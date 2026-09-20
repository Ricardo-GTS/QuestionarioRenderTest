"""Fluxo completo (equivalente a backend/tests/test_api_flow.py + test_admin_flow.py
+ test_report_reputation.py), agora contra views Django + templates ao inves de
uma API JSON. Roda contra o Postgres+pgvector real (nao ha skip automatico aqui
porque o ambiente de dev ja tem o banco disponivel)."""

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.moderation.models import Report, ReportStatus
from apps.questions.models import Question, QuestionStatus
from apps.quiz.models import QuizAttempt


@pytest.mark.django_db
def test_dedupe_by_semantic_similarity(client, fake_embedding):
    client.post(
        reverse("accounts:register"),
        {"name": "Autor", "email": "autor@example.com", "password": "senha1234"},
    )

    statement = "A capital da Franca e Paris"
    resp = client.post(reverse("questions:create"), {"statement": statement, "correct_answer": "true", "category": ""})
    assert resp.status_code == 200
    assert Question.objects.count() == 1

    # Mesmo enunciado -> mesmo embedding (fake determinístico) -> similaridade 1.0 >= threshold
    resp = client.post(reverse("questions:create"), {"statement": statement, "correct_answer": "false", "category": ""})
    assert resp.status_code == 200
    assert Question.objects.count() == 1  # descartada, nao duplicou
    assert resp.context["similar_questions"]


@pytest.mark.django_db
def test_quiz_report_and_moderation_flow(client, fake_embedding):
    # Autor cria uma pergunta
    client.post(reverse("accounts:register"), {"name": "Autor", "email": "autor2@example.com", "password": "senha1234"})
    client.post(
        reverse("questions:create"),
        {"statement": "O Sol e uma estrela", "correct_answer": "true", "category": "Ciencias"},
    )
    question = Question.objects.get(statement="O Sol e uma estrela")
    client.post(reverse("accounts:logout"))

    # Aluno faz o quiz
    client.post(reverse("accounts:register"), {"name": "Aluno", "email": "aluno@example.com", "password": "senha1234"})
    resp = client.get(reverse("quiz:start"))
    assert resp.status_code == 200
    assert resp.context["question"].id == question.id

    resp = client.post(reverse("quiz:answer"), {"answer": "true"})
    assert resp.headers.get("HX-Redirect") == reverse("quiz:result")

    resp = client.get(reverse("quiz:result"))
    assert resp.context["result"]["score"] == 1
    assert resp.context["result"]["total"] == 1
    assert QuizAttempt.objects.filter(user__email="aluno@example.com", score=1, total=1).exists()

    # Aluno reporta a pergunta
    resp = client.post(
        reverse("moderation:report_question", args=[question.id]),
        {"reason_category": "Pergunta duplicada", "reason": ""},
    )
    assert Report.objects.filter(question=question, reason_category="Pergunta duplicada").exists()

    # Reportar de novo deve falhar (unique constraint / regra de negocio)
    resp = client.post(
        reverse("moderation:report_question", args=[question.id]),
        {"reason_category": "Fora do tema", "reason": ""},
    )
    assert Report.objects.filter(question=question).count() == 1
    client.post(reverse("accounts:logout"))

    # Admin resolve a fila de moderacao
    client.post(reverse("accounts:register"), {"name": "Admin", "email": "admin@example.com", "password": "senha1234"})
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
    client.post(reverse("accounts:register"), {"name": "Aluno", "email": "aluno3@example.com", "password": "senha1234"})
    resp = client.get(reverse("moderation:pending_reports"))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_settings_update():
    from apps.core.services import get_effective_settings

    User.objects.create_user(email="admin@example.com", name="Admin", password="senha1234")
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
