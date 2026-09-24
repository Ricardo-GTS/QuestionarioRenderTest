"""Semestres isolados em schemas (django-tenants)."""

import pytest
from django.db import connection
from django.urls import reverse
from django_tenants.utils import schema_context, schema_exists

from apps.accounts.models import User
from apps.core.models import Enrollment, Semester
from apps.core.semesters import SemesterError, open_new_semester, schema_name_for, suggest_next_name
from apps.questions.models import Question, Topic
from conftest import _fake_get_embedding


def test_suggest_next_name_and_schema_name():
    assert suggest_next_name("2026.1") == "2026.2"
    assert suggest_next_name("2026.2") == "2027.1"
    assert suggest_next_name("turma A") == ""
    assert schema_name_for("2026.2") == "s2026_2"


def _question(author, statement, topic="Geral"):
    return Question.objects.create(
        author=author, statement=statement, correct_answer=True, topic=topic,
        citations_references="r", pertinence="p", embedding=_fake_get_embedding(statement),
    )


def _admin_client(client):
    admin = User.objects.create_user(email="admin@example.com", name="Admin", password="x" * 8, registration_number="99990000")
    client.force_login(admin)
    return admin


@pytest.fixture
def old_data():
    """Dados no semestre ativo de teste (2026.1), que vai virar o 'anterior'."""
    student = User.objects.create_user(email="aluno@example.com", name="Aluno", password="x" * 8, registration_number="10000001")
    author = User.objects.create_user(email="autor@example.com", name="Autor", password="x" * 8, registration_number="10000002")
    Topic.objects.create(name="Geografia")
    question = _question(author, "A capital do Brasil e Brasilia", topic="Geografia")
    return {"student": student, "author": author, "question": question}


def _open(name="2026.2", copy_topics=True):
    connection.set_schema_to_public()
    return open_new_semester(name=name, copy_topics=copy_topics, backup_done=True)


@pytest.mark.django_db
def test_open_new_semester_isolates_and_copies(old_data):
    old = Semester.objects.get(is_active=True)
    new = _open()
    old.refresh_from_db()
    assert new.is_active and not old.is_active and old.closed_at is not None
    assert Semester.objects.filter(is_active=True).count() == 1
    assert schema_exists("s2026_2")
    assert (new.similarity_threshold, new.quiz_size, new.report_threshold) == (
        old.similarity_threshold, old.quiz_size, old.report_threshold,
    )
    with schema_context("s2026_2"):
        assert Question.objects.count() == 0  # comeca do zero
        assert list(Topic.objects.values_list("name", flat=True)) == ["Geografia"]  # topicos copiados
    with schema_context(old.schema_name):
        assert Question.objects.count() == 1  # antigo intacto


@pytest.mark.django_db
def test_open_without_copying_topics_and_validation(old_data):
    with pytest.raises(SemesterError):
        open_new_semester(name="2026.2", copy_topics=True, backup_done=False)
    with pytest.raises(SemesterError):
        open_new_semester(name="semestre novo", copy_topics=True, backup_done=True)
    with pytest.raises(SemesterError):
        open_new_semester(name="2026.1", copy_topics=True, backup_done=True)  # ja' existe
    _open(copy_topics=False)
    with schema_context("s2026_2"):
        assert Topic.objects.count() == 0


@pytest.mark.django_db
def test_student_after_new_semester(client, old_data, fake_embedding):
    _open()
    client.force_login(old_data["student"])
    # conta antiga: cai em "Participar"
    resp = client.get(reverse("quiz:start"))
    assert resp.status_code == 302 and resp.url == reverse("accounts:join_semester")
    assert client.get(reverse("quiz:start"), HTTP_HX_REQUEST="true")["HX-Redirect"] == reverse("accounts:join_semester")
    client.post(reverse("accounts:join_semester"))
    assert Enrollment.objects.filter(user=old_data["student"], semester__name="2026.2").exists()

    # tudo do zero: quiz sem questoes, Minhas Questoes/Estatisticas vazias
    assert client.get(reverse("quiz:start")).context["no_questions"]
    assert list(client.get(reverse("questions:mine")).context["page"]) == []
    assert client.get(reverse("accounts:stats")).context["stats"]["summary"]["answered"] == 0
    # questao do semestre antigo nao existe aqui
    assert client.get(reverse("questions:comments_panel", args=[old_data["question"].id])).status_code == 404

    # duplicata so' dentro do semestre: igual a uma do antigo e' aceita
    resp = client.post(
        reverse("questions:create"),
        {"statement": "A capital do Brasil e Brasilia", "correct_answer": "true", "topic": "Geografia",
         "citations_references": "r", "pertinence": "p"},
    )
    assert resp.context["success_message"]
    with schema_context("s2026_2"):
        assert Question.objects.count() == 1


@pytest.mark.django_db
def test_new_account_is_enrolled_automatically(client, old_data):
    _open()
    user = User.objects.create_user(email="novo@example.com", name="Novo", password="x" * 8, registration_number="20000001")
    assert Enrollment.objects.filter(user=user, semester__name="2026.2").exists()
    client.force_login(user)
    assert client.get(reverse("quiz:start")).status_code == 200


@pytest.mark.django_db
def test_admin_selector_and_reactivate(client, old_data):
    _admin_client(client)
    _open()
    old = Semester.objects.get(name="2026.1")
    # admin nao precisa participar; ve o ativo (2026.2, vazio) por padrao
    resp = client.get(reverse("moderation:topic_list"))
    assert resp.status_code == 200
    # seleciona o encerrado: ve os dados antigos + aviso; o ativo nao muda
    client.post(reverse("core:select_semester"), {"semester": old.id, "next": reverse("moderation:dashboard")})
    resp = client.get(reverse("moderation:dashboard"))
    assert resp.context["stats"]["active_questions"] == 1
    assert "(encerrado)" in resp.content.decode()
    assert Semester.objects.get(is_active=True).name == "2026.2"
    users = [u["email"] for u in client.get(reverse("accounts:admin_user_list")).context["users"]]
    assert "aluno@example.com" in users
    # "next" externo e' ignorado (sem open redirect)
    resp = client.post(reverse("core:select_semester"), {"semester": old.id, "next": "https://evil.example.com/"})
    assert resp.url == reverse("moderation:dashboard")
    # reativar desfaz
    client.post(reverse("core:reactivate_semester", args=[old.id]))
    assert Semester.objects.get(is_active=True).name == "2026.1"


@pytest.mark.django_db
def test_semesters_page_requires_admin(client, old_data):
    client.force_login(old_data["student"])
    assert client.get(reverse("core:semesters")).status_code == 403
    assert client.post(reverse("core:open_semester"), {"name": "2026.2", "backup_done": "1"}).status_code == 403


@pytest.mark.django_db
def test_semesters_page_open_requires_backup_checkbox(client, old_data):
    _admin_client(client)
    resp = client.post(reverse("core:open_semester"), {"name": "2026.2", "copy_topics": "1"})
    assert "backup" in resp.context["error"]
    resp = client.post(reverse("core:open_semester"), {"name": "2026.2", "copy_topics": "1", "backup_done": "1"})
    assert resp.status_code == 302
    assert Semester.objects.get(is_active=True).name == "2026.2"


@pytest.mark.django_db
def test_delete_user_with_data_in_two_semesters(client, old_data):
    from apps.accounts.services import delete_user_everywhere

    author = old_data["author"]
    _open()
    with schema_context("s2026_2"):
        _question(author, "Questao do autor no semestre novo")
    delete_user_everywhere(author)
    assert not User.objects.filter(pk=author.pk).exists()
    for schema in ("s2026_1", "s2026_2"):
        with schema_context(schema):
            assert not Question.objects.filter(author_id=author.pk).exists()


@pytest.mark.django_db
def test_vector_extension_lives_in_public():
    with connection.cursor() as cursor:
        cursor.execute("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'")
        assert cursor.fetchone()[0] == "public"


@pytest.mark.django_db
def test_no_active_semester_page(client):
    Semester.objects.update(is_active=False)
    user = User.objects.create_user(email="x@example.com", name="X", password="x" * 8, registration_number="30000001")
    client.force_login(user)
    resp = client.get(reverse("quiz:start"))
    assert resp.status_code == 503
    assert "Nenhum semestre aberto" in resp.content.decode()
    assert client.get(reverse("accounts:account")).status_code == 200  # conta funciona sem semestre
