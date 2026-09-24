"""Envio de e-mail em background (EMAIL_SEND_ASYNC) e rate limit com cache compartilhado."""

from unittest import mock

import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts import services
from apps.accounts.models import EmailSendLog, PendingRegistration

REGISTER = {"name": "Aluno", "email": "aluno@example.com", "password": "senha1234", "registration_number": "20230012345"}


class _InlineThread:
    """Substitui threading.Thread: roda o alvo na hora do start() (teste deterministico)."""

    started = 0

    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        _InlineThread.started += 1
        self.target()


@pytest.fixture
def async_email(settings, monkeypatch):
    settings.EMAIL_SEND_ASYNC = True
    _InlineThread.started = 0
    monkeypatch.setattr(services.threading, "Thread", _InlineThread)
    # A thread "inline" roda na conexao do proprio teste; o close_all() do fim do envio
    # (correto numa thread real, que tem conexao propria) fecharia a transacao do teste.
    monkeypatch.setattr(services.connections, "close_all", lambda: None)
    return _InlineThread


# Sem transaction=True: com os semestres em schemas (django-tenants), o flush de um
# teste transacional apagaria o semestre de teste. Os callbacks de on_commit (onde a
# thread e' disparada) rodam via django_capture_on_commit_callbacks.
@pytest.mark.django_db
def test_async_send_runs_in_background_thread(client, async_email, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse("accounts:register"), REGISTER)
    assert resp.url == reverse("accounts:confirm_registration")
    assert async_email.started == 1
    assert len(mail.outbox) == 1
    assert EmailSendLog.objects.count() == 1


@pytest.mark.django_db
def test_async_send_failure_removes_send_log_so_resend_is_free(client, async_email, django_capture_on_commit_callbacks):
    with mock.patch("apps.accounts.services.send_mail", side_effect=OSError("smtp down")):
        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(reverse("accounts:register"), REGISTER)
    # em background a tela nao sabe da falha na hora...
    assert resp.url == reverse("accounts:confirm_registration")
    # ...mas o log sumiu, entao o reenvio fica liberado imediatamente
    assert not EmailSendLog.objects.exists()
    assert PendingRegistration.objects.count() == 1
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("accounts:resend_registration_code"))
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_sync_dispatch_returns_result():
    calls = []
    assert services.dispatch_email(lambda: True) is True
    assert services.dispatch_email(lambda: False, on_failure=lambda: calls.append(1)) is False
    assert calls == [1]
