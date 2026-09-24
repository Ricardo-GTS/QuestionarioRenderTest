"""Pagina "Minhas Questoes": o autor acompanha as proprias questoes, estatistica de
acerto, motivos dos reportes (anonimos), comentarios e selos de novidades."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.moderation.models import Report
from apps.questions import services
from apps.questions.models import Question, QuestionAnswer, QuestionComment, QuestionStatus
from conftest import _fake_get_embedding


def _user(email, reg):
    return User.objects.create_user(email=email, name=email.split("@")[0].title(), password="x" * 8, registration_number=reg)


def _question(author, statement, status=QuestionStatus.ACTIVE, correct=True):
    return Question.objects.create(
        author=author, statement=statement, correct_answer=correct, topic="Geral",
        citations_references="ref", pertinence="p", embedding=_fake_get_embedding(statement), status=status,
    )


@pytest.fixture
def author_client(client):
    author = _user("autor@example.com", "10000001")
    client.force_login(author)
    return client, author


def _page(client, **params):
    return client.get(reverse("questions:mine"), params)


def _answer_in_quiz(user, question, answer=True):
    """Responde a questao no quiz real (o que grava o QuestionAnswer)."""
    c = Client()
    c.force_login(user)
    session = c.session
    session["quiz_question_ids"] = [question.id]
    session["quiz_answers"] = {}
    session["quiz_position"] = 0
    session.save()
    c.post(reverse("quiz:answer"), {"answer": "true" if answer else "false", "question_id": question.id})
    return c


# --- funcoes puras ---


def test_can_view_comments_with_author():
    assert services.can_view_comments(is_admin=False, answered_in_quiz=False, has_own_visible_comment=False, is_author=True)


def test_accuracy_label():
    assert services.accuracy_label(0, 0) == "Ainda não foi respondida"
    assert services.accuracy_label(1, 1).startswith("Respondida 1 vez (acerto aparece")
    assert "%" not in services.accuracy_label(4, 3)
    assert services.accuracy_label(6, 4) == "Respondida 6 vezes · 67% de acerto"


def test_comments_open():
    assert services.comments_open(Question(status=QuestionStatus.ACTIVE))
    assert services.comments_open(Question(status=QuestionStatus.REPORTED))
    assert not services.comments_open(Question(status=QuestionStatus.REMOVED))


# --- pagina ---


@pytest.mark.django_db
def test_lists_only_own_questions_and_filters(author_client):
    client, author = author_client
    other = _user("outro@example.com", "10000002")
    _question(author, "Minha ativa")
    _question(author, "Minha em analise", QuestionStatus.REPORTED)
    _question(author, "Minha removida", QuestionStatus.REMOVED)
    _question(other, "De outro autor")

    resp = _page(client)
    statements = [q.statement for q in resp.context["page"]]
    assert "De outro autor" not in statements
    assert len(statements) == 3
    assert dict((k, c) for k, _, c in resp.context["filters"]) == {"todas": 3, "ativas": 1, "em-analise": 1, "removidas": 1}

    assert [q.statement for q in _page(client, situacao="em-analise").context["page"]] == ["Minha em analise"]
    html = _page(client, situacao="em-analise").content.decode()
    assert "Em análise" in html and "fora do treino" in html
    # filtro invalido cai em "todas"
    assert _page(client, situacao="xyz").context["situacao"] == "todas"


@pytest.mark.django_db
def test_pagination_and_invalid_page(author_client):
    client, author = author_client
    for i in range(25):
        _question(author, f"Questao {i}")
    assert len(_page(client).context["page"]) == 20
    assert len(_page(client, pagina=2).context["page"]) == 5
    assert _page(client, pagina=99).context["page"].number == 2
    assert _page(client, pagina="abc").status_code == 200


@pytest.mark.django_db
def test_accuracy_counts_once_per_quiz(author_client):
    client, author = author_client
    q = _question(author, "Estatistica")
    for i in range(5):
        student = _user(f"aluno{i}@example.com", f"2000000{i}")
        c = _answer_in_quiz(student, q, answer=(i < 4))
        # repetir o POST no mesmo quiz nao conta de novo
        c.post(reverse("quiz:answer"), {"answer": "true", "question_id": q.id})
    assert QuestionAnswer.objects.filter(question=q).count() == 5
    [item] = _page(client).context["page"]
    assert item.accuracy == "Respondida 5 vezes · 80% de acerto"


@pytest.mark.django_db
def test_report_reasons_shown_without_reporter_name(author_client):
    client, author = author_client
    q = _question(author, "Reportada")
    reporter = User.objects.create_user(email="dedoduro@example.com", name="Fulano Dedoduro", password="x" * 8, registration_number="30000001")
    Report.objects.create(question=q, reporter=reporter, reason="A resposta esta errada")
    html = _page(client).content.decode()
    assert "A resposta esta errada" in html
    assert "1 reporte" in html and "Pendente" in html
    assert "Dedoduro" not in html and "dedoduro@example.com" not in html


@pytest.mark.django_db
def test_query_count_does_not_grow_with_questions(author_client, django_assert_max_num_queries):
    client, author = author_client
    for i in range(5):
        _question(author, f"Q{i}")
    with django_assert_max_num_queries(25) as small:
        _page(client)
    for i in range(5, 20):
        _question(author, f"Q{i}")
    with django_assert_max_num_queries(len(small.captured_queries)):
        _page(client)


# --- comentarios ---


@pytest.mark.django_db
def test_author_opens_own_question_comments_and_gets_author_badge(author_client):
    client, author = author_client
    q = _question(author, "Com comentarios")
    student = _user("aluno@example.com", "20000001")
    s = _answer_in_quiz(student, q)
    s.post(reverse("questions:comments_panel", args=[q.id]), {"text": "Duvida do aluno"})

    resp = client.get(reverse("questions:comments_panel", args=[q.id]))  # sem responder nem comentar
    assert resp.status_code == 200
    client.post(reverse("questions:comments_panel", args=[q.id]), {"text": "Resposta do autor"})
    html = s.get(reverse("questions:comments_panel", args=[q.id])).content.decode()
    blocks = {("Resposta do autor" in b, "Autor da questão" in b) for b in html.split('class="comment"')[1:]}
    assert blocks == {(True, True), (False, False)}  # selo so' no comentario do autor


@pytest.mark.django_db
def test_removed_question_is_read_only(author_client):
    client, author = author_client
    q = _question(author, "Vai ser removida")
    client.post(reverse("questions:comments_panel", args=[q.id]), {"text": "Antes de remover"})
    q.status = QuestionStatus.REMOVED
    q.save()
    resp = client.post(reverse("questions:comments_panel", args=[q.id]), {"text": "Depois de remover"})
    html = resp.content.decode()
    assert "só para leitura" in html
    assert "Enviar comentário" not in html
    assert not QuestionComment.objects.filter(text="Depois de remover").exists()
    # apagar o proprio continua funcionando
    mine = QuestionComment.objects.get(text="Antes de remover")
    assert client.post(reverse("questions:delete_comment", args=[mine.id])).status_code == 200
    assert not QuestionComment.objects.filter(pk=mine.id).exists()


# --- selos ---


@pytest.mark.django_db
def test_new_badges_on_page_and_menu(author_client):
    client, author = author_client
    q1, q2 = _question(author, "Q um"), _question(author, "Q dois")
    student = _user("aluno@example.com", "20000001")
    for q in (q1, q2):
        s = _answer_in_quiz(student, q)
        s.post(reverse("questions:comments_panel", args=[q.id]), {"text": f"comentario em {q.statement}"})
    client.post(reverse("questions:comments_panel", args=[q1.id]), {"text": "o autor tambem comenta"})  # marca q1 como vista

    resp = _page(client)
    by_statement = {q.statement: q.new_count for q in resp.context["page"]}
    assert by_statement == {"Q um": 0, "Q dois": 1}
    assert resp.context["my_questions_new_comments"] == 1
    assert "Minhas Questões" in resp.content.decode()

    client.get(reverse("questions:comments_panel", args=[q2.id]))  # abrir zera
    assert _page(client).context["my_questions_new_comments"] == 0


@pytest.mark.django_db
def test_menu_badge_absent_for_anonymous(client):
    resp = client.get(reverse("accounts:login"))
    assert resp.context["my_questions_new_comments"] == 0


@pytest.mark.django_db
def test_interactions_excludes_own_questions(author_client):
    client, author = author_client
    own = _question(author, "Propria")
    client.post(reverse("questions:comments_panel", args=[own.id]), {"text": "comentei na minha"})
    assert list(client.get(reverse("accounts:interactions")).context["questions"]) == []


@pytest.mark.django_db
def test_deleted_user_keeps_question_stats(author_client):
    client, author = author_client
    q = _question(author, "Historico")
    student = _user("aluno@example.com", "20000001")
    _answer_in_quiz(student, q)
    student.delete()
    answer = QuestionAnswer.objects.get(question=q)
    assert answer.user is None
    [item] = _page(client).context["page"]
    assert item.answer_count == 1
