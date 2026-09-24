"""Comentarios na questao (painel do quiz e Minhas interacoes), reporte de comentario,
moderacao dos comentarios reportados e reporte da questao pelo painel."""

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.moderation.models import Report
from apps.questions import services
from apps.questions.models import CommentReport, CommentReportStatus, CommentSeen, Question, QuestionComment
from conftest import _fake_get_embedding


def _user(email, reg):
    return User.objects.create_user(email=email, name=email.split("@")[0].title(), password="x" * 8, registration_number=reg)


@pytest.fixture
def setup(client):
    """Questao de um autor + aluno logado que ja' respondeu essa questao no quiz."""
    author = _user("autor@example.com", "10000001")
    question = Question.objects.create(
        author=author, statement="O Sol e uma estrela", correct_answer=True, topic="Ciencias",
        citations_references="ref", pertinence="p", embedding=_fake_get_embedding("sol"),
    )
    student = _user("aluno@example.com", "10000002")
    client.force_login(student)
    client.get(reverse("quiz:start"))
    client.post(reverse("quiz:answer"), {"answer": "true", "question_id": question.id})
    return {"author": author, "question": question, "student": student}


def _panel(client, question):
    return client.get(reverse("questions:comments_panel", args=[question.id]))


def _comment(client, question, text="Boa pergunta"):
    return client.post(reverse("questions:comments_panel", args=[question.id]), {"text": text})


def _other_student_client(question, email="outro@example.com", reg="10000003", answer=True):
    other = Client()
    user = _user(email, reg)
    other.force_login(user)
    if answer:
        other.get(reverse("quiz:start"))
        other.post(reverse("quiz:answer"), {"answer": "true", "question_id": question.id})
    return other, user


# --- regra pura ---


def test_can_view_comments_rule():
    assert services.can_view_comments(is_admin=True, answered_in_quiz=False, has_own_visible_comment=False)
    assert services.can_view_comments(is_admin=False, answered_in_quiz=True, has_own_visible_comment=False)
    assert services.can_view_comments(is_admin=False, answered_in_quiz=False, has_own_visible_comment=True)
    assert not services.can_view_comments(is_admin=False, answered_in_quiz=False, has_own_visible_comment=False)


# --- acesso ---


@pytest.mark.django_db
def test_without_answering_panel_is_forbidden(setup):
    other, _ = _other_student_client(setup["question"], answer=False)
    assert _panel(other, setup["question"]).status_code == 403
    assert _comment(other, setup["question"]).status_code == 403
    assert not QuestionComment.objects.exists()


@pytest.mark.django_db
def test_answered_student_sees_others_and_comments(client, setup):
    q = setup["question"]
    other, _ = _other_student_client(q)
    _comment(other, q, "Comentario do outro")
    resp = _panel(client, q)
    assert resp.status_code == 200
    assert "Comentario do outro" in resp.content.decode()
    resp = _comment(client, q, "Meu comentario")
    html = resp.content.decode()
    assert "Meu comentario" in html and "Comentario do outro" in html
    assert QuestionComment.objects.filter(author=setup["student"]).count() == 1


@pytest.mark.django_db
def test_after_quiz_only_commented_questions_stay_visible(client, setup):
    q = setup["question"]
    q2 = Question.objects.create(
        author=setup["author"], statement="A Lua e um planeta", correct_answer=False, topic="Ciencias",
        citations_references="ref", pertinence="p", embedding=_fake_get_embedding("lua"),
    )
    _comment(client, q, "Comentei aqui")
    # fim do quiz: a sessao do quiz e' limpa
    for key in ("quiz_question_ids", "quiz_answers", "quiz_position", "quiz_started_at"):
        session = client.session
        session.pop(key, None)
        session.save()
    assert _panel(client, q).status_code == 200  # comentou -> continua vendo
    assert _panel(client, q2).status_code == 403  # nao comentou nem respondeu agora


@pytest.mark.django_db
@pytest.mark.parametrize("text", ["", "   ", "x" * 1001])
def test_invalid_comment_is_rejected(client, setup, text):
    resp = _comment(client, setup["question"], text)
    assert resp.status_code == 200
    assert resp.context["form"].errors.get("text")
    assert not QuestionComment.objects.exists()


@pytest.mark.django_db
def test_comment_html_is_escaped(client, setup):
    resp = _comment(client, setup["question"], "<script>alert(1)</script>")
    html = resp.content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.django_db
def test_author_deletes_own_but_not_others_admin_removes_any(client, setup):
    q = setup["question"]
    other, _ = _other_student_client(q)
    _comment(other, q, "Do outro")
    _comment(client, q, "Meu")
    mine = QuestionComment.objects.get(text="Meu")
    theirs = QuestionComment.objects.get(text="Do outro")

    assert client.post(reverse("questions:delete_comment", args=[theirs.id])).status_code == 403
    assert client.post(reverse("questions:delete_comment", args=[mine.id])).status_code == 200
    assert not QuestionComment.objects.filter(pk=mine.id).exists()  # autor: some de vez

    admin = Client()
    admin.force_login(_user("admin@example.com", "10000009"))
    assert admin.post(reverse("questions:delete_comment", args=[theirs.id])).status_code == 200
    theirs.refresh_from_db()
    assert theirs.removed  # admin: oculta
    assert "Do outro" not in _panel(client, q).content.decode()


@pytest.mark.django_db
def test_comment_rate_limit_per_user(client, setup, settings):
    settings.RATELIMIT_ENABLE = True
    cache.clear()
    codes = [_comment(client, setup["question"], f"comentario {i}").status_code for i in range(11)]
    cache.clear()
    assert codes[:10] == [200] * 10
    assert codes[10] == 429


# --- reporte de comentario e moderacao ---


def _report_comment(client, comment, category="Entrega a resposta", reason=""):
    return client.post(
        reverse("questions:report_comment", args=[comment.id]), {"reason_category": category, "reason": reason}
    )


@pytest.mark.django_db
def test_report_comment_rules_and_moderation(client, setup):
    q = setup["question"]
    other, other_user = _other_student_client(q)
    _comment(other, q, "A resposta e verdadeiro")
    comment = QuestionComment.objects.get()

    # "Outro" sem texto e' recusado
    resp = _report_comment(client, comment, "Outro", "")
    assert resp.context["form"].errors.get("reason")
    # nao da pra reportar o proprio
    assert "próprio" in _report_comment(other, comment).context["error"]
    # reporta; segunda vez e' recusada
    assert _report_comment(client, comment).context["sent"] is True
    assert "já reportou" in _report_comment(client, comment).context["error"]
    assert CommentReport.objects.count() == 1
    assert 'Reportado' in _panel(client, q).content.decode()

    # fila de moderacao: aluno nao acessa; admin ve e remove
    assert client.get(reverse("moderation:pending_comment_reports")).status_code == 403
    admin = Client()
    admin.force_login(_user("admin@example.com", "10000009"))
    resp = admin.get(reverse("moderation:pending_comment_reports"))
    assert comment in [item["comment"] for item in resp.context["items"]]
    admin.post(reverse("moderation:remove_reported_comment", args=[comment.id]))
    comment.refresh_from_db()
    assert comment.removed
    assert CommentReport.objects.get().status == CommentReportStatus.ACCEPTED
    assert admin.get(reverse("moderation:pending_comment_reports")).context["items"] == []


@pytest.mark.django_db
def test_keep_reported_comment_rejects_reports(client, setup):
    q = setup["question"]
    other, _ = _other_student_client(q)
    _comment(other, q, "Comentario normal")
    comment = QuestionComment.objects.get()
    _report_comment(client, comment, "Spam ou fora do tema")
    admin = Client()
    admin.force_login(_user("admin@example.com", "10000009"))
    admin.post(reverse("moderation:keep_reported_comment", args=[comment.id]))
    comment.refresh_from_db()
    assert not comment.removed
    assert CommentReport.objects.get().status == CommentReportStatus.REJECTED


# --- Minhas interacoes ---


@pytest.mark.django_db
def test_interactions_lists_commented_questions_with_new_badge(client, setup):
    q = setup["question"]
    page = client.get(reverse("accounts:interactions"))
    assert list(page.context["questions"]) == []

    _comment(client, q, "Meu comentario")  # abrir/comentar marca como visto
    other, _ = _other_student_client(q)
    _comment(other, q, "Resposta do outro 1")
    _comment(other, q, "Resposta do outro 2")

    page = client.get(reverse("accounts:interactions"))
    [item] = page.context["questions"]
    assert item.id == q.id
    assert item.comment_count == 3
    assert item.new_count == 2  # so' os dos outros, depois da ultima visita
    assert "2 novos" in page.content.decode()

    _panel(client, q)  # abrir o painel zera o selo
    [item] = client.get(reverse("accounts:interactions")).context["questions"]
    assert item.new_count == 0
    assert CommentSeen.objects.filter(user=setup["student"], question=q).exists()


@pytest.mark.django_db
def test_interactions_my_reports_status(client, setup):
    q = setup["question"]
    Report.objects.create(question=q, reporter=setup["student"], reason_category="Fora do tema", status="accepted")
    page = client.get(reverse("accounts:interactions"))
    assert "Aceito — a questão foi removida" in page.content.decode()


# --- reporte da questao pelo painel do quiz ---


@pytest.mark.django_db
def test_report_question_panel(client, setup):
    q = setup["question"]
    url = reverse("moderation:report_question", args=[q.id]) + "?painel=1"
    other, _ = _other_student_client(q, answer=False)
    assert other.get(url).status_code == 403

    resp = client.get(url)
    assert resp.status_code == 200
    assert "Enviar reporte" in resp.content.decode()
    resp = client.post(
        reverse("moderation:report_question", args=[q.id]),
        {"reason_category": "Resposta incorreta", "reason": "", "painel": "1"},
    )
    assert "Reporte enviado" in resp.content.decode()
    assert Report.objects.filter(question=q, reporter=setup["student"]).count() == 1
    assert "já reportou" in client.get(url).content.decode()


@pytest.mark.django_db
def test_report_requires_login(setup):
    anonymous = Client()
    resp = anonymous.post(reverse("moderation:report_question", args=[setup["question"].id]), {"reason_category": "Outro"})
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp.url
