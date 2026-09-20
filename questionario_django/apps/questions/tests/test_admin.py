"""Regressao: VectorField (numpy array) nao pode ir em readonly_fields direto no
Django Admin -- display_for_field faz "value in field.empty_values", que quebra
com ValueError ("truth value of an array... ambiguous") numa comparacao elementwise."""

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.questions.models import Question


@pytest.mark.django_db
def test_question_admin_change_page_renders(client, fake_embedding):
    from apps.questions.services import get_embedding

    author = User.objects.create_user(email="autor@example.com", name="Autor", password="senha1234")
    superuser = User.objects.create_superuser(email="super@example.com", name="Super", password="senha1234")
    question = Question.objects.create(
        author=author,
        statement="Pergunta de teste",
        correct_answer=True,
        embedding=get_embedding("Pergunta de teste"),
    )

    client.force_login(superuser)
    resp = client.get(reverse("admin:questions_question_change", args=[question.id]))
    assert resp.status_code == 200
