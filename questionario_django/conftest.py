"""Fixtures compartilhadas -- porte de backend/tests/conftest.py.

ADMIN_EMAILS e o embedding deterministico sao equivalentes ao padrao usado nos
testes de integracao do backend FastAPI (fixture `client`), para nao depender
de Ollama/Google reais durante os testes.
"""

import pytest
from django.test import Client


@pytest.fixture(autouse=True)
def _admin_emails(settings):
    settings.ADMIN_EMAILS = {"admin@example.com"}
    settings.RATELIMIT_ENABLE = False
    # E-mail sincrono nos testes (o background/thread tem teste proprio).
    settings.EMAIL_SEND_ASYNC = False


def _fake_get_embedding(text: str) -> list[float]:
    from apps.questions.models import EMBEDDING_DIM

    seed = float(sum(ord(c) for c in text) % 1000)
    return [seed] + [0.0] * (EMBEDDING_DIM - 1)


@pytest.fixture
def fake_embedding(monkeypatch):
    """Mock de apps.questions.services.get_embedding -- embedding determinístico
    por hash simples do texto, mesma tecnica do backend/tests/conftest.py."""
    monkeypatch.setattr("apps.questions.services.get_embedding", _fake_get_embedding)
    return _fake_get_embedding


@pytest.fixture
def client():
    return Client()


def register_user(client, data):
    """Cadastro completo pelo fluxo real: POST do cadastro, le o codigo do e-mail
    (pytest-django usa o backend locmem -> django.core.mail.outbox) e confirma.
    Se o cadastro for recusado (form invalido), devolve essa resposta sem confirmar."""
    import re

    from django.core import mail
    from django.urls import reverse

    resp = client.post(reverse("accounts:register"), data)
    if resp.status_code != 302 or resp.url != reverse("accounts:confirm_registration"):
        return resp
    message = next(m for m in reversed(mail.outbox) if data["email"] in m.to)
    code = re.search(r"\b(\d{6})\b", message.body).group(1)
    return client.post(reverse("accounts:confirm_registration"), {"code": code})
