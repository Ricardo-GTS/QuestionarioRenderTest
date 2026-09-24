"""Fluxo completo (equivalente a backend/tests/test_api_flow.py + test_admin_flow.py
+ test_report_reputation.py), agora contra views Django + templates ao inves de
uma API JSON. Roda contra o Postgres+pgvector real (nao ha skip automatico aqui
porque o ambiente de dev ja tem o banco disponivel)."""

import pytest
from conftest import register_user
from django.urls import reverse

from apps.accounts.models import User
from apps.moderation.forms import QuestionEditForm
from apps.moderation.models import Report, ReportStatus
from apps.questions.forms import NEW_TOPIC_CHOICE
from apps.questions.models import Question, QuestionStatus
from apps.quiz.models import QuizAttempt


@pytest.mark.django_db
def test_dedupe_by_semantic_similarity(client, fake_embedding):
    register_user(
        client,
        {"name": "Autor", "email": "autor@example.com", "password": "senha1234", "registration_number": "20250000001"},
    )

    statement = "A capital da Franca e Paris"
    payload = {
        "statement": statement,
        "correct_answer": "true",
        "topic": NEW_TOPIC_CHOICE,
        "new_topic": "Geografia",
        "citations_references": "Wikipedia",
        "pertinence": "Testa conhecimento geografico basico",
    }
    resp = client.post(reverse("questions:create"), payload)
    assert resp.status_code == 200
    assert Question.objects.count() == 1

    # Mesmo enunciado -> mesmo embedding (fake determinístico) -> similaridade 1.0 >= threshold
    resp = client.post(reverse("questions:create"), {**payload, "correct_answer": "false"})
    assert resp.status_code == 200
    assert Question.objects.count() == 1  # descartada, nao duplicou
    assert resp.context["similar_questions"]


@pytest.mark.django_db
def test_question_create_topic_select_offers_existing_topics_and_reuses_them(client, fake_embedding):
    # Semeia um topico existente via ORM, com status != active para nao colidir
    # com a busca de similaridade (o embedding fake e sempre colinear entre si,
    # entao qualquer pergunta *ativa* pre-existente seria sempre detectada como
    # "similar" a qualquer nova pergunta -- limitacao do fake, nao do produto real).
    author = User.objects.create_user(email="seed@example.com", name="Seed", password="senha1234")
    Question.objects.create(
        author=author,
        statement="Pergunta semente sobre biologia",
        correct_answer=True,
        topic="Biologia",
        citations_references="Livro de Biologia",
        pertinence="Semente",
        embedding=fake_embedding("Pergunta semente sobre biologia"),
        status=QuestionStatus.REMOVED,
    )

    register_user(
        client,
        {"name": "Autor", "email": "autor-topico@example.com", "password": "senha1234", "registration_number": "20250000002"},
    )

    resp = client.get(reverse("questions:create"))
    assert ("Biologia", "Biologia") in resp.context["form"].fields["topic"].choices

    resp = client.post(
        reverse("questions:create"),
        {
            "statement": "Mitocondrias sao a usina de energia da celula",
            "correct_answer": "true",
            "topic": "Biologia",
            "citations_references": "Livro de Biologia",
            "pertinence": "Conceito basico de biologia",
        },
    )
    assert resp.status_code == 200
    question = Question.objects.get(statement="Mitocondrias sao a usina de energia da celula")
    assert question.topic == "Biologia"


@pytest.mark.django_db
def test_question_create_requires_new_topic_text_when_selected(client, fake_embedding):
    register_user(
        client,
        {"name": "Autor", "email": "autor-topico-vazio@example.com", "password": "senha1234", "registration_number": "20250000003"},
    )
    resp = client.post(
        reverse("questions:create"),
        {
            "statement": "Pergunta sem topico definido",
            "correct_answer": "true",
            "topic": NEW_TOPIC_CHOICE,
            "new_topic": "",
            "citations_references": "Fonte",
            "pertinence": "Motivo",
        },
    )
    assert resp.status_code == 200
    assert resp.context["form"].errors.get("new_topic")
    assert not Question.objects.filter(statement="Pergunta sem topico definido").exists()


@pytest.mark.django_db
def test_question_create_stores_citations_and_pertinence(client, fake_embedding):
    register_user(
        client,
        {"name": "Autor", "email": "autor-citacoes@example.com", "password": "senha1234", "registration_number": "20250000004"},
    )

    resp = client.post(
        reverse("questions:create"),
        {
            "statement": "Testes de software provam a ausencia de bugs",
            "correct_answer": "false",
            "topic": NEW_TOPIC_CHOICE,
            "new_topic": "Testes",
            "citations_references": "Dijkstra -- Testes mostram a presenca de bugs, nao a ausencia.",
            "pertinence": "Avalia a compreensao da limitacao inerente dos testes.",
        },
    )
    assert resp.status_code == 200
    question = Question.objects.get(statement="Testes de software provam a ausencia de bugs")
    assert question.citations_references == "Dijkstra -- Testes mostram a presenca de bugs, nao a ausencia."
    assert question.pertinence == "Avalia a compreensao da limitacao inerente dos testes."


@pytest.mark.django_db
def test_admin_edit_question_updates_citations_and_pertinence(client, fake_embedding):
    register_user(client, {"name": "Autor", "email": "autor-edit@example.com", "password": "senha1234", "registration_number": "20250000005"})
    client.post(
        reverse("questions:create"),
        {
            "statement": "Pergunta original",
            "correct_answer": "true",
            "topic": NEW_TOPIC_CHOICE,
            "new_topic": "Geral",
            "citations_references": "Fonte original",
            "pertinence": "Motivo original",
        },
    )
    question = Question.objects.get(statement="Pergunta original")
    client.post(reverse("accounts:logout"))

    register_user(client, {"name": "Admin", "email": "admin@example.com", "password": "senha1234", "registration_number": "20250000006"})
    resp = client.post(
        reverse("moderation:edit_question", args=[question.id]),
        {
            "statement": "Pergunta original",
            "correct_answer": "true",
            "topic": "Geral",
            "citations_references": "Fonte X, pagina 10",
            "pertinence": "Cobra um conceito central do capitulo",
        },
    )
    assert resp.status_code == 200
    question.refresh_from_db()
    assert question.citations_references == "Fonte X, pagina 10"
    assert question.pertinence == "Cobra um conceito central do capitulo"


@pytest.mark.django_db
def test_admin_edit_question_topic_select_offers_choices_and_allows_new_topic(client, fake_embedding):
    register_user(client, {"name": "Autor", "email": "autor-edit-topico@example.com", "password": "senha1234", "registration_number": "20250000007"})
    client.post(
        reverse("questions:create"),
        {
            "statement": "Pergunta sobre topico antigo",
            "correct_answer": "true",
            "topic": NEW_TOPIC_CHOICE,
            "new_topic": "Topico Antigo",
            "citations_references": "Fonte",
            "pertinence": "Motivo",
        },
    )
    question = Question.objects.get(statement="Pergunta sobre topico antigo")
    client.post(reverse("accounts:logout"))

    register_user(client, {"name": "Admin", "email": "admin@example.com", "password": "senha1234", "registration_number": "20250000008"})

    form = QuestionEditForm()
    assert ("Topico Antigo", "Topico Antigo") in form.fields["topic"].choices
    assert (NEW_TOPIC_CHOICE, "Novo Tópico") in form.fields["topic"].choices

    # Selecionar "Novo Topico" sem preencher o texto -> erro, topico nao muda
    resp = client.post(
        reverse("moderation:edit_question", args=[question.id]),
        {
            "statement": question.statement,
            "correct_answer": "true",
            "topic": NEW_TOPIC_CHOICE,
            "new_topic": "",
            "citations_references": question.citations_references,
            "pertinence": question.pertinence,
        },
    )
    assert resp.status_code == 200
    assert resp.context["form"].errors.get("new_topic")
    question.refresh_from_db()
    assert question.topic == "Topico Antigo"

    # Selecionar "Novo Topico" com texto -> atualiza o topico da pergunta
    resp = client.post(
        reverse("moderation:edit_question", args=[question.id]),
        {
            "statement": question.statement,
            "correct_answer": "true",
            "topic": NEW_TOPIC_CHOICE,
            "new_topic": "Topico Novo",
            "citations_references": question.citations_references,
            "pertinence": question.pertinence,
        },
    )
    assert resp.status_code == 200
    question.refresh_from_db()
    assert question.topic == "Topico Novo"


@pytest.mark.django_db
def test_quiz_report_and_moderation_flow(client, fake_embedding):
    # Autor cria uma pergunta
    register_user(client, {"name": "Autor", "email": "autor2@example.com", "password": "senha1234", "registration_number": "20250000009"})
    client.post(
        reverse("questions:create"),
        {
            "statement": "O Sol e uma estrela",
            "correct_answer": "true",
            "topic": NEW_TOPIC_CHOICE,
            "new_topic": "Ciencias",
            "citations_references": "Livro de Astronomia",
            "pertinence": "Conceito basico de astronomia",
        },
    )
    question = Question.objects.get(statement="O Sol e uma estrela")
    client.post(reverse("accounts:logout"))

    # Aluno faz o quiz
    register_user(client, {"name": "Aluno", "email": "aluno@example.com", "password": "senha1234", "registration_number": "20250000010"})
    resp = client.get(reverse("quiz:start"))
    assert resp.status_code == 200
    assert resp.context["question"].id == question.id

    resp = client.post(reverse("quiz:answer"), {"answer": "true", "question_id": question.id})
    assert resp.context["answered"] and resp.context["is_correct"]
    resp = client.post(reverse("quiz:next"), {"question_id": question.id})
    assert resp.headers.get("HX-Redirect") == reverse("quiz:result")

    resp = client.get(reverse("quiz:result"))
    assert resp.context["result"]["score"] == 1
    assert resp.context["result"]["total"] == 1
    assert QuizAttempt.objects.filter(user__email="aluno@example.com", score=1, total=1).exists()

    # Aluno reporta a pergunta
    resp = client.post(
        reverse("moderation:report_question", args=[question.id]),
        {"reason": "Pergunta duplicada de outra"},
    )
    assert Report.objects.filter(question=question, reason="Pergunta duplicada de outra").exists()

    # Reportar de novo deve falhar (unique constraint / regra de negocio)
    resp = client.post(
        reverse("moderation:report_question", args=[question.id]),
        {"reason": "Fora do tema"},
    )
    assert Report.objects.filter(question=question).count() == 1
    client.post(reverse("accounts:logout"))

    # Admin resolve a fila de moderacao
    register_user(client, {"name": "Admin", "email": "admin@example.com", "password": "senha1234", "registration_number": "20250000011"})
    resp = client.get(reverse("moderation:pending_reports"))
    assert resp.status_code == 200
    assert question in [item["question"] for item in resp.context["items"]]

    resp = client.post(reverse("moderation:approve_removal", args=[question.id]))
    question.refresh_from_db()
    assert question.status == QuestionStatus.REMOVED
    assert Report.objects.get(question=question).status == ReportStatus.ACCEPTED

    # Reputacao refletida para o aluno (reportou, aceito) e o autor (pergunta removida)
    resp = client.get(reverse("accounts:admin_user_list"))
    users_by_email = {u["email"]: u for u in resp.context["users"]}
    assert users_by_email["aluno@example.com"]["accepted_reports_count"] == 1
    assert users_by_email["autor2@example.com"]["questions_removed_count"] == 1


@pytest.mark.django_db
def test_non_admin_cannot_access_moderation_queue(client):
    register_user(client, {"name": "Aluno", "email": "aluno3@example.com", "password": "senha1234", "registration_number": "20250000012"})
    resp = client.get(reverse("moderation:pending_reports"))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_settings_update():
    from apps.core.services import get_effective_settings

    User.objects.create_user(
        email="admin@example.com", name="Admin", password="senha1234", registration_number="20259999999"
    )
    from django.test import Client

    client = Client()
    client.login(username="admin@example.com", password="senha1234")

    resp = client.post(
        reverse("moderation:admin_settings"),
        {"similarity_threshold": "0.8", "quiz_size": "5", "report_threshold": "2"},
    )
    assert resp.status_code in (302, 200)
    current = get_effective_settings()
    assert current.similarity_threshold == 0.8
    assert current.quiz_size == 5
    assert current.report_threshold == 2


def _make_question(author, statement, topic):
    from conftest import _fake_get_embedding

    return Question.objects.create(
        author=author,
        statement=statement,
        correct_answer=True,
        topic=topic,
        citations_references="ref",
        pertinence="pert",
        embedding=_fake_get_embedding(statement),
    )


@pytest.mark.django_db
def test_admin_topic_create_rename_delete(client):
    from apps.questions.models import Topic

    register_user(client, {"name": "Admin", "email": "admin@example.com", "password": "senha1234", "registration_number": "20250000013"})
    admin = User.objects.get(email="admin@example.com")
    _make_question(admin, "Pergunta de fisica", "Fisica")

    # Adicionar: topico sem pergunta aparece no select de criacao de pergunta
    resp = client.post(reverse("moderation:topic_create"), {"name": "Quimica"})
    assert resp.status_code == 302
    assert Topic.objects.filter(name="Quimica").exists()
    resp = client.get(reverse("questions:create"))
    assert ("Quimica", "Quimica") in resp.context["form"].fields["topic"].choices

    # Adicionar duplicado (inclusive topico que so' existe em perguntas) -> erro
    resp = client.post(reverse("moderation:topic_create"), {"name": "Fisica"})
    assert resp.status_code == 200
    assert "já existe" in resp.context["error"]

    # Renomear: atualiza as perguntas que usam o topico
    resp = client.post(reverse("moderation:topic_rename"), {"topic": "Fisica", "new_name": "Fisica Basica"})
    assert resp.status_code == 302
    assert Question.objects.get(statement="Pergunta de fisica").topic == "Fisica Basica"

    # Renomear para nome existente -> recusado
    resp = client.post(reverse("moderation:topic_rename"), {"topic": "Fisica Basica", "new_name": "Quimica"})
    assert resp.status_code == 200
    assert resp.context["error"]
    assert Question.objects.get(statement="Pergunta de fisica").topic == "Fisica Basica"

    # Excluir topico em uso sem destino -> recusado
    resp = client.post(reverse("moderation:topic_delete"), {"topic": "Fisica Basica"})
    assert resp.status_code == 200
    assert resp.context["error"]

    # Excluir movendo as perguntas para outro topico
    resp = client.post(reverse("moderation:topic_delete"), {"topic": "Fisica Basica", "mode": "move", "reassign_to": "Quimica"})
    assert resp.status_code == 302
    assert Question.objects.get(statement="Pergunta de fisica").topic == "Quimica"
    names = [t["name"] for t in client.get(reverse("moderation:topic_list")).context["topics"]]
    assert names == ["Quimica"]

    # Excluir topico sem perguntas
    Question.objects.all().delete()
    resp = client.post(reverse("moderation:topic_delete"), {"topic": "Quimica"})
    assert resp.status_code == 302
    assert not Topic.objects.exists()


@pytest.mark.django_db
def test_topic_management_requires_admin(client):
    register_user(client, {"name": "Aluno", "email": "aluno-topico@example.com", "password": "senha1234", "registration_number": "20250000014"})
    resp = client.post(reverse("moderation:topic_create"), {"name": "Hack"})
    assert resp.status_code in (302, 403)
    from apps.questions.models import Topic

    assert not Topic.objects.exists()


@pytest.mark.django_db
def test_admin_topic_delete_with_questions(client):
    from apps.questions.models import Topic

    register_user(client, {"name": "Admin", "email": "admin@example.com", "password": "senha1234", "registration_number": "20250000015"})
    admin = User.objects.get(email="admin@example.com")
    _make_question(admin, "Pergunta de historia 1", "Historia")
    _make_question(admin, "Pergunta de historia 2", "Historia")
    _make_question(admin, "Pergunta de artes", "Artes")
    Topic.objects.create(name="Historia")

    resp = client.post(reverse("moderation:topic_delete"), {"topic": "Historia", "mode": "delete_questions"})
    assert resp.status_code == 302
    assert not Question.objects.filter(topic="Historia").exists()
    assert not Topic.objects.filter(name="Historia").exists()
    assert Question.objects.filter(topic="Artes").count() == 1
    names = [t["name"] for t in client.get(reverse("moderation:topic_list")).context["topics"]]
    assert names == ["Artes"]
