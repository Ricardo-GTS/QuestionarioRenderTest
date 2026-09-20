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


def _fake_get_embedding(text: str) -> list[float]:
    seed = float(sum(ord(c) for c in text) % 1000)
    return [seed] + [0.0] * 767


@pytest.fixture
def fake_embedding(monkeypatch):
    """Mock de apps.questions.services.get_embedding -- embedding determinístico
    por hash simples do texto, mesma tecnica do backend/tests/conftest.py."""
    monkeypatch.setattr("apps.questions.services.get_embedding", _fake_get_embedding)
    return _fake_get_embedding


@pytest.fixture
def client():
    return Client()
