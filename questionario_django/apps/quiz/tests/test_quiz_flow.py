"""Quiz de treino: resposta na hora, "Proxima" so' depois de responder, protecao contra
clique duplo/outra aba, retomada, vencimento e pergunta apagada no meio."""

import time

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.questions.models import Question
from apps.quiz.services import QUIZ_TTL_SECONDS, current_position, quiz_expired
from conftest import _fake_get_embedding


def _question(author, statement, correct=True):
    return Question.objects.create(
        author=author,
        statement=statement,
        correct_answer=correct,
        topic="Geral",
        citations_references="Livro X, cap. 2",
        pertinence="p",
        embedding=_fake_get_embedding(statement),
    )


@pytest.fixture
def quiz(client, settings):
    """Aluno logado com um quiz de 3 perguntas (de outro autor) ja' iniciado."""
    from apps.core.models import AppSettings

    app_settings = AppSettings.get_solo()
    app_settings.quiz_size = 3
    app_settings.save()
    author = User.objects.create_user(email="autor@example.com", name="Autor", password="x" * 8, registration_number="11110000")
    for i in range(3):
        _question(author, f"Pergunta numero {i}", correct=(i % 2 == 0))
    student = User.objects.create_user(email="aluno@example.com", name="Aluno", password="x" * 8, registration_number="22220000")
    client.force_login(student)
    resp = client.get(reverse("quiz:start"))
    return resp


def _answer(client, qid, answer="true"):
    return client.post(reverse("quiz:answer"), {"answer": answer, "question_id": qid})


def _next(client, qid):
    return client.post(reverse("quiz:next"), {"question_id": qid})


# --- funcoes puras ---


def test_current_position_compat_with_old_sessions():
    assert current_position([1, 2, 3], {"1": True}, None) == 1  # sessao antiga: 1a sem resposta
    assert current_position([1, 2, 3], {"1": True}, 0) == 0  # respondeu, ainda nao clicou Proxima
    assert current_position([1, 2], {}, 9) == 2


def test_quiz_expired():
    now = time.time()
    assert not quiz_expired(None, now)
    assert not quiz_expired(now - 60, now)
    assert quiz_expired(now - QUIZ_TTL_SECONDS - 1, now)


# --- fluxo ---


@pytest.mark.django_db
def test_unanswered_card_has_no_next_comments_or_report(client, quiz):
    html = quiz.content.decode()
    assert quiz.context["answered"] is False
    assert reverse("quiz:next") not in html
    assert "Comentários" not in html
    assert "Reportar" not in html
    assert "Verdadeiro" in html


@pytest.mark.django_db
def test_answer_shows_correct_answer_and_does_not_advance(client, quiz):
    q = quiz.context["question"]
    resp = _answer(client, q.id, "false" if q.correct_answer else "true")
    assert resp.context["question"].id == q.id  # nao avancou sozinho
    assert resp.context["answered"] is True
    assert resp.context["is_correct"] is False
    html = resp.content.decode()
    assert "Você errou" in html
    assert "Resposta correta" in html
    assert "Livro X, cap. 2" in html
    assert reverse("quiz:next") in html
    assert "Comentários (0)" in html
    assert "Reportar" in html


@pytest.mark.django_db
def test_answer_cannot_be_changed(client, quiz):
    q = quiz.context["question"]
    _answer(client, q.id, "true")
    resp = _answer(client, q.id, "false")
    assert resp.context["given_answer"] is True
    assert client.session["quiz_answers"][str(q.id)] is True


@pytest.mark.django_db
def test_next_requires_answer(client, quiz):
    q = quiz.context["question"]
    resp = _next(client, q.id)
    assert resp.context["question"].id == q.id
    assert resp.context["answered"] is False


@pytest.mark.django_db
def test_double_click_on_next_advances_once(client, quiz):
    ids = client.session["quiz_question_ids"]
    _answer(client, ids[0])
    first = _next(client, ids[0])
    second = _next(client, ids[0])  # 2o clique, ainda com o id da pergunta 1
    assert first.context["question"].id == ids[1]
    assert second.context["question"].id == ids[1]
    assert second.context["answered"] is False


@pytest.mark.django_db
def test_stale_tab_answer_is_ignored(client, quiz):
    ids = client.session["quiz_question_ids"]
    resp = _answer(client, ids[1])  # id de outra pergunta (aba desatualizada)
    assert resp.context["question"].id == ids[0]
    assert client.session["quiz_answers"] == {}


@pytest.mark.django_db
def test_last_next_goes_to_result(client, quiz):
    ids = client.session["quiz_question_ids"]
    for qid in ids:
        _answer(client, qid)
        resp = _next(client, qid)
    assert resp["HX-Redirect"] == reverse("quiz:result")
    result = client.get(reverse("quiz:result"))
    assert result.context["result"]["total"] == 3


@pytest.mark.django_db
def test_reload_resumes_and_novo_restarts(client, quiz):
    ids = client.session["quiz_question_ids"]
    _answer(client, ids[0])
    _next(client, ids[0])
    resp = client.get(reverse("quiz:start"))
    assert resp.context["question"].id == ids[1]
    assert resp.context["index"] == 2
    resp = client.get(reverse("quiz:start") + "?novo=1")
    assert resp.context["index"] == 1
    assert client.session["quiz_answers"] == {}


@pytest.mark.django_db
def test_expired_quiz_restarts(client, quiz):
    ids = client.session["quiz_question_ids"]
    _answer(client, ids[0])
    _next(client, ids[0])
    session = client.session
    session["quiz_started_at"] = time.time() - QUIZ_TTL_SECONDS - 1
    session.save()
    resp = client.get(reverse("quiz:start"))
    assert resp.context["index"] == 1
    assert client.session["quiz_answers"] == {}


@pytest.mark.django_db
def test_old_session_without_position_works(client, quiz):
    ids = client.session["quiz_question_ids"]
    session = client.session
    session["quiz_answers"] = {str(ids[0]): True}
    del session["quiz_position"]
    del session["quiz_started_at"]
    session.save()
    resp = client.get(reverse("quiz:start"))
    assert resp.context["question"].id == ids[1]


@pytest.mark.django_db
def test_question_deleted_mid_quiz_is_skipped(client, quiz):
    ids = client.session["quiz_question_ids"]
    Question.objects.filter(pk=ids[0]).delete()
    resp = client.get(reverse("quiz:start"))
    assert resp.status_code == 200
    assert resp.context["question"].id == ids[1]
    assert resp.context["total"] == 2
