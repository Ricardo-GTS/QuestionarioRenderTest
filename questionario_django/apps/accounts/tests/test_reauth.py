"""Pagina Conta: trocar e-mail ou senha exige confirmar a identidade com um codigo
enviado ao e-mail atual (vale REAUTH_MINUTES). O nome continua editavel direto."""

import re
import time
from datetime import timedelta

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.accounts import services
from apps.accounts.models import EmailChangeRequest, EmailSendLog, ReauthRequest, User

EMAIL = "aluno@example.com"


def _login(client, **extra):
    user = User.objects.create_user(
        email=EMAIL, name="Aluno", password="senha1234", registration_number="20230012345", **extra
    )
    client.force_login(user)
    return user


def _last_code():
    message = next(m for m in reversed(mail.outbox) if EMAIL in m.to)
    return re.search(r"\b(\d{6})\b", message.body).group(1)


def _reauth(client):
    client.post(reverse("accounts:reauth_start"))
    return client.post(reverse("accounts:confirm_reauth"), {"code": _last_code()})


def _save(client, **fields):
    return client.post(reverse("accounts:account"), {"name": "Aluno", "email": EMAIL, "password": "", **fields})


def test_reauth_seconds_left():
    now = time.time()
    assert services.reauth_seconds_left(None, now) == 0
    assert services.reauth_seconds_left(now - 1, now) == 0
    assert services.reauth_seconds_left(now + 30, now) == 30


@pytest.mark.django_db
def test_without_code_email_and_password_are_locked_but_name_saves(client):
    user = _login(client)
    page = client.get(reverse("accounts:account"))
    assert page.context["form"].fields["email"].disabled
    assert page.context["form"].fields["password"].disabled
    assert "Enviar código para alterar" in page.content.decode()

    # POST forcado com e-mail/senha novos: so' o nome muda
    resp = _save(client, name="Novo Nome", email="outro@example.com", password="senhanova123")
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.name == "Novo Nome"
    assert user.email == EMAIL
    assert user.check_password("senha1234")
    assert not EmailChangeRequest.objects.exists()


@pytest.mark.django_db
def test_code_goes_to_current_email_and_unlocks(client):
    user = _login(client)
    resp = client.post(reverse("accounts:reauth_start"))
    assert resp.url == reverse("accounts:confirm_reauth")
    assert mail.outbox[-1].to == [EMAIL]
    assert "alterar" in mail.outbox[-1].subject.lower()

    wrong = f"{(int(_last_code()) + 1) % 10**6:06d}"
    resp = client.post(reverse("accounts:confirm_reauth"), {"code": wrong})
    assert resp.status_code == 200
    assert not client.get(reverse("accounts:account")).context["reauthenticated"]

    resp = client.post(reverse("accounts:confirm_reauth"), {"code": _last_code()})
    assert resp.url == reverse("accounts:account")
    assert not ReauthRequest.objects.exists()
    page = client.get(reverse("accounts:account"))
    assert page.context["reauthenticated"]
    assert not page.context["form"].fields["password"].disabled

    _save(client, password="senhanova123")
    user.refresh_from_db()
    assert user.check_password("senhanova123")


@pytest.mark.django_db
def test_password_change_keeps_this_session_logs_out_others_and_notifies(client, django_capture_on_commit_callbacks):
    user = _login(client)
    other = Client()
    other.force_login(user)
    _reauth(client)
    with django_capture_on_commit_callbacks(execute=True):
        _save(client, password="senhanova123")
    assert client.get(reverse("accounts:account")).status_code == 200
    assert other.get(reverse("accounts:account")).status_code == 302
    assert any("senha foi alterada" in m.subject for m in mail.outbox)


@pytest.mark.django_db
def test_unlock_expires(client):
    user = _login(client)
    _reauth(client)
    session = client.session
    session["reauth_until"] = time.time() - 1
    session.save()
    _save(client, password="senhanova123")
    user.refresh_from_db()
    assert user.check_password("senha1234")


@pytest.mark.django_db
def test_email_change_needs_unlock_and_new_email_code(client):
    user = _login(client)
    _reauth(client)
    resp = _save(client, email="novo@example.com")
    assert resp.url == reverse("accounts:confirm_email_change")
    user.refresh_from_db()
    assert user.email == EMAIL  # so' muda com o codigo do novo e-mail
    assert mail.outbox[-1].to == ["novo@example.com"]


@pytest.mark.django_db
def test_google_only_account_uses_same_flow(client):
    user = _login(client, google_sub="g-1")
    user.set_unusable_password()
    user.save()
    client.force_login(user)
    _reauth(client)
    _save(client, password="senhanova123")
    user.refresh_from_db()
    assert user.check_password("senhanova123")


@pytest.mark.django_db
def test_reauth_resend_cooldown_and_page_guard(client):
    _login(client)
    assert client.get(reverse("accounts:confirm_reauth")).url == reverse("accounts:account")
    client.post(reverse("accounts:reauth_start"))
    client.post(reverse("accounts:resend_reauth_code"))
    assert len(mail.outbox) == 1
    for log in EmailSendLog.objects.all():
        log.sent_at -= timedelta(seconds=services.RESEND_COOLDOWN_SECONDS + 1)
        log.save(update_fields=["sent_at"])
    client.post(reverse("accounts:resend_reauth_code"))
    assert len(mail.outbox) == 2
