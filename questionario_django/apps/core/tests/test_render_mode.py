"""Build de teste do Render: modo sem embeddings (EMBEDDINGS_DISABLED) e CSRF atras de
proxy HTTPS."""

from unittest import mock

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.questions import services
from apps.questions.models import EMBEDDING_DIM, Question

STATEMENT = "Scrum define sprints de duração fixa."


@pytest.fixture
def no_embeddings(settings):
    settings.EMBEDDINGS_DISABLED = True


def _payload(topic):
    return {
        "statement": STATEMENT,
        "correct_answer": "true",
        "topic": topic,
        "new_topic": "Processos" if topic == "__new_topic__" else "",
        "citations_references": "Valente, cap. 2",
        "pertinence": "Base do Scrum",
    }


def test_hash_embedding_is_deterministic_and_normalized(no_embeddings):
    with mock.patch("apps.questions.services.httpx.post") as post:
        first = services.get_embedding(STATEMENT)
        second = services.get_embedding(STATEMENT)
    post.assert_not_called()
    assert first == second
    assert len(first) == EMBEDDING_DIM
    assert abs(sum(v * v for v in first) - 1.0) < 1e-9
    assert services.get_embedding("outra frase") != first


@pytest.mark.django_db
def test_duplicate_questions_are_accepted(client, no_embeddings):
    user = User.objects.create_user(email="aluno@example.com", name="Aluno", password="x" * 8, registration_number="22220000")
    client.force_login(user)
    client.post(reverse("questions:create"), _payload("__new_topic__"))
    resp = client.post(reverse("questions:create"), _payload("Processos"))
    assert Question.objects.filter(statement=STATEMENT).count() == 2
    assert "Modo de teste" in client.get(reverse("questions:create")).content.decode()
    assert resp.status_code == 200


@pytest.mark.django_db
def test_notice_hidden_in_normal_mode(client):
    user = User.objects.create_user(email="aluno@example.com", name="Aluno", password="x" * 8, registration_number="22220000")
    client.force_login(user)
    assert "Modo de teste" not in client.get(reverse("questions:create")).content.decode()


@pytest.mark.django_db
def test_health_reports_disabled_without_calling_ollama(client, no_embeddings):
    with mock.patch("apps.core.views.httpx.get") as get:
        data = client.get(reverse("core:health")).json()
    get.assert_not_called()
    assert data == {"status": "ok", "checks": {"database": "ok", "ollama": "disabled"}}


def test_warm_ollama_skips(no_embeddings, capsys):
    with mock.patch("apps.questions.services.httpx.post") as post:
        call_command("warm_ollama", attempts=1, wait=0)
    post.assert_not_called()
    assert "desligados" in capsys.readouterr().out


@pytest.mark.django_db
def test_csrf_behind_https_proxy(settings):
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    settings.CSRF_TRUSTED_ORIGINS = ["https://*.onrender.com"]
    settings.ALLOWED_HOSTS = [".onrender.com"]
    client = Client(enforce_csrf_checks=True)
    host = "questionario.onrender.com"
    client.get(reverse("accounts:login"), HTTP_HOST=host, HTTP_X_FORWARDED_PROTO="https")
    token = client.cookies["csrftoken"].value
    data = {"email": "ninguem@example.com", "password": "errada123", "csrfmiddlewaretoken": token}
    ok = client.post(reverse("accounts:login"), data, HTTP_HOST=host, HTTP_X_FORWARDED_PROTO="https",
                     HTTP_ORIGIN=f"https://{host}", HTTP_REFERER=f"https://{host}/entrar")
    assert ok.status_code != 403
    bad = client.post(reverse("accounts:login"), data, HTTP_HOST=host, HTTP_X_FORWARDED_PROTO="https",
                      HTTP_ORIGIN="https://malicioso.example.com", HTTP_REFERER="https://malicioso.example.com/")
    assert bad.status_code == 403
