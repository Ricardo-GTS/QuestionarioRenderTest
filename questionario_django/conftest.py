"""Fixtures compartilhadas -- porte de backend/tests/conftest.py.

ADMIN_EMAILS e o embedding deterministico sao equivalentes ao padrao usado nos
testes de integracao do backend FastAPI (fixture `client`), para nao depender
de Ollama/Google reais durante os testes.
"""

import pytest
from django.test import Client


TEST_SEMESTER = {"name": "2026.1", "schema_name": "s2026_1"}


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Semestres (django-tenants): o banco de teste so' tem o schema public depois do
    migrate; cria UM semestre ativo (schema + migrations das apps por semestre) pra
    sessao inteira."""
    with django_db_blocker.unblock():
        from django.conf import settings as dj_settings
        from django.db import connection

        from apps.core.models import Domain, Semester

        connection.set_schema_to_public()
        semester = Semester(
            is_active=True,
            similarity_threshold=dj_settings.SIMILARITY_THRESHOLD,
            quiz_size=dj_settings.QUIZ_SIZE,
            report_threshold=dj_settings.REPORT_THRESHOLD,
            **TEST_SEMESTER,
        )
        semester.save(verbosity=0)
        Domain.objects.create(domain="s2026_1.semestre.local", tenant=semester, is_primary=True)


@pytest.fixture(autouse=True)
def _active_semester_schema(request):
    """Todo teste com banco roda dentro do schema do semestre ativo (como o
    SemesterMiddleware faz em cada request)."""
    if request.node.get_closest_marker("django_db") is None and "db" not in request.fixturenames:
        yield
        return
    request.getfixturevalue("db")
    from django.db import connection

    from apps.core.models import Semester

    connection.set_schema_to_public()
    connection.set_tenant(Semester.objects.get(is_active=True))
    yield
    connection.set_schema_to_public()


@pytest.fixture(autouse=True)
def _admin_emails(settings, tmp_path_factory):
    settings.ADMIN_EMAILS = {"admin@example.com"}
    settings.RATELIMIT_ENABLE = False
    # E-mail sincrono nos testes (o background/thread tem teste proprio).
    settings.EMAIL_SEND_ASYNC = False
    # Planilhas de backup numa pasta temporaria, gravadas na hora (sem thread).
    settings.QUESTION_SHEETS_DIR = str(tmp_path_factory.mktemp("planilhas"))
    settings.QUESTION_SHEETS_ASYNC = False


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
