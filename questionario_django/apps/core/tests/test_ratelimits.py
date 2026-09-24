"""Rate limit por alvo (e-mail/usuario), com teto alto por IP: uma turma inteira atras
do mesmo IP (NAT da universidade) tem que conseguir entrar."""

import pytest
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import User
from apps.core import ratelimits


@pytest.fixture
def ratelimit_on(settings, monkeypatch):
    """Liga o rate limit e congela o relogio dele: a janela do django-ratelimit e' fixa
    (blocos de 60 s), e um teste com centenas de requests podia cruzar a virada da
    janela e zerar o contador no meio (teste instavel)."""
    import time as real_time
    from types import SimpleNamespace

    import django_ratelimit.core

    frozen = real_time.time()
    monkeypatch.setattr(django_ratelimit.core, "time", SimpleNamespace(time=lambda: frozen))
    settings.RATELIMIT_ENABLE = True
    cache.clear()
    yield
    cache.clear()


def _login(client, email, password="errada"):
    return client.post(reverse("accounts:login"), {"email": email, "password": password}).status_code


@pytest.mark.django_db
def test_shared_cache_backend(settings):
    # com varios workers gunicorn, o contador precisa ser o mesmo pra todos
    assert settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.db.DatabaseCache"


@pytest.mark.django_db
def test_60_students_same_ip_can_all_log_in(client, ratelimit_on):
    for i in range(60):
        User.objects.create_user(
            email=f"aluno{i}@example.com", name=f"Aluno {i}", password="senha1234", registration_number=f"2023{i:08d}"
        )
    codes = [_login(client, f"aluno{i}@example.com", "senha1234") for i in range(60)]
    assert codes == [302] * 60


@pytest.mark.django_db
def test_login_limited_per_email_not_per_ip(client, ratelimit_on):
    codes = [_login(client, "vitima@example.com") for _ in range(6)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429
    # variar maiusculas/espacos nao escapa do limite
    assert _login(client, "  VITIMA@example.com ") == 429
    # outro e-mail do mesmo IP continua livre
    assert _login(client, "outro@example.com") == 200


@pytest.mark.django_db
def test_ip_ceiling_still_blocks_mass_abuse(client, ratelimit_on):
    """Cada pedido usa um e-mail diferente (escapa do limite por alvo), mas o teto de
    300/min por IP, somando as telas de conta, segura o abuso em massa."""
    limit = int(ratelimits.IP_CEILING.split("/")[0])
    codes = [
        client.post(reverse("accounts:password_reset_request"), {"identifier": f"x{i}@example.com"}).status_code
        for i in range(limit + 1)
    ]
    assert 429 not in codes[:limit]
    assert codes[limit] == 429


@pytest.mark.django_db
def test_question_creation_limited_per_user(client, ratelimit_on, fake_embedding):
    user = User.objects.create_user(email="autor@example.com", name="Autor", password="senha1234", registration_number="20230000001")
    client.force_login(user)
    codes = [
        client.post(
            reverse("questions:create"),
            {
                "statement": f"Pergunta numero {i} " * 3,
                "correct_answer": "true",
                "topic": "__new_topic__",
                "new_topic": "Geral",
                "citations_references": "ref",
                "pertinence": "pert",
            },
        ).status_code
        for i in range(21)
    ]
    assert codes[:20] == [200] * 20
    assert codes[20] == 429


def test_client_ip_ignores_forwarded_header_without_proxy(settings):
    settings.TRUSTED_PROXY_COUNT = 0
    req = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4")
    assert ratelimits.client_ip(req) == "10.0.0.1"


def test_client_ip_behind_one_trusted_proxy(settings):
    settings.TRUSTED_PROXY_COUNT = 1
    # cliente forjou "6.6.6.6"; o proxy anotou o IP real (8.8.8.8) no fim
    req = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 8.8.8.8")
    assert ratelimits.client_ip(req) == "8.8.8.8"
    req = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1")
    assert ratelimits.client_ip(req) == "10.0.0.1"
