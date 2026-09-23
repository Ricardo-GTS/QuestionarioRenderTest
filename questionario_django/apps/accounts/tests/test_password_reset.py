"""Recuperacao de senha ("Esqueci minha senha") por codigo enviado ao e-mail da conta."""

import re
from datetime import timedelta

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import EmailSendLog, PasswordResetRequest, User

EMAIL = "aluno@example.com"
NEW_PASSWORD = "novasenha123"


def _user(**extra):
    return User.objects.create_user(
        email=EMAIL, name="Aluno", password="senhaantiga", registration_number="20230012345", **extra
    )


def _last_code():
    message = next(m for m in reversed(mail.outbox) if EMAIL in m.to)
    return re.search(r"\b(\d{6})\b", message.body).group(1)


def _wrong(code):
    return f"{(int(code) + 1) % 10**6:06d}"


def _request_reset(client, email=EMAIL):
    return client.post(reverse("accounts:password_reset_request"), {"identifier": email})


def _confirm(client, code, password=NEW_PASSWORD, confirm=None):
    return client.post(
        reverse("accounts:password_reset_confirm"),
        {"code": code, "new_password": password, "new_password_confirm": confirm or password},
    )


@pytest.mark.django_db
def test_login_page_links_to_password_reset(client):
    assert reverse("accounts:password_reset_request") in client.get(reverse("accounts:login")).content.decode()


@pytest.mark.django_db
def test_reset_with_code_changes_password_logs_in_and_notifies(client, django_capture_on_commit_callbacks):
    user = _user()
    resp = _request_reset(client, "  Aluno@Example.com ")
    assert resp.url == reverse("accounts:password_reset_confirm")
    assert len(mail.outbox) == 1
    assert "redefinir" in mail.outbox[0].subject.lower()
    page = client.get(reverse("accounts:password_reset_confirm"))
    assert "a***@example.com" in page.content.decode()

    with django_capture_on_commit_callbacks(execute=True):
        resp = _confirm(client, _last_code())
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert not user.check_password("senhaantiga")
    assert not PasswordResetRequest.objects.exists()
    assert client.get(reverse("questions:create")).status_code == 200  # ja' logado
    assert any("senha foi alterada" in m.subject for m in mail.outbox)


@pytest.mark.django_db
def test_reset_logs_out_other_sessions(client):
    _user()
    other = Client()
    other.login(username=EMAIL, password="senhaantiga")
    assert other.get(reverse("questions:create")).status_code == 200

    _request_reset(client)
    _confirm(client, _last_code())
    resp = other.get(reverse("questions:create"))
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp.url


@pytest.mark.django_db
def test_unknown_email_gets_same_response_and_no_email(client):
    _user()
    known = _request_reset(client)
    unknown = _request_reset(Client(), "ninguem@example.com")
    assert known.status_code == unknown.status_code == 302
    assert known.url == unknown.url
    assert len(mail.outbox) == 1  # so' o da conta que existe

    other = Client()
    _request_reset(other, "ninguem@example.com")
    resp = _confirm(other, "123456")
    assert resp.status_code == 200
    assert resp.context["form"].errors["code"][0] == _confirm(client, _wrong(_last_code())).context["form"].errors["code"][0]
    assert not User.objects.filter(email="ninguem@example.com").exists()


@pytest.mark.django_db
def test_wrong_code_is_limited_to_5_attempts(client):
    user = _user()
    _request_reset(client)
    code = _last_code()
    for _ in range(services.MAX_ATTEMPTS):
        assert _confirm(client, _wrong(code)).status_code == 200
    # esgotado: nem o codigo certo passa mais
    assert _confirm(client, code).status_code == 200
    user.refresh_from_db()
    assert user.check_password("senhaantiga")


@pytest.mark.django_db
def test_expired_code_is_rejected(client):
    user = _user()
    _request_reset(client)
    code = _last_code()
    PasswordResetRequest.objects.update(code_expires_at=timezone.now() - timedelta(seconds=1))
    assert _confirm(client, code).status_code == 200
    user.refresh_from_db()
    assert user.check_password("senhaantiga")


@pytest.mark.django_db
def test_password_confirmation_must_match_and_min_length(client):
    user = _user()
    _request_reset(client)
    code = _last_code()
    resp = _confirm(client, code, confirm="outrasenha123")
    assert resp.context["form"].errors.get("new_password_confirm")
    resp = _confirm(client, code, password="curta", confirm="curta")
    assert resp.context["form"].errors.get("new_password")
    user.refresh_from_db()
    assert user.check_password("senhaantiga")


@pytest.mark.django_db
def test_resend_respects_cooldown_and_invalidates_old_code(client):
    user = _user()
    _request_reset(client)
    old_code = _last_code()
    client.post(reverse("accounts:password_reset_resend"))
    assert len(mail.outbox) == 1  # antes dos 60 s

    for log in EmailSendLog.objects.all():
        log.sent_at -= timedelta(seconds=services.RESEND_COOLDOWN_SECONDS + 1)
        log.save(update_fields=["sent_at"])
    client.post(reverse("accounts:password_reset_resend"))
    assert len(mail.outbox) == 2
    new_code = _last_code()
    if new_code != old_code:
        assert _confirm(client, old_code).status_code == 200
    assert _confirm(client, new_code).status_code == 302
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_google_only_account_can_set_password(client):
    user = User.objects.create_user(
        email=EMAIL, name="Aluno", password=None, google_sub="g-123", registration_number="20230012345"
    )
    assert not user.has_usable_password()
    _request_reset(client)
    assert _confirm(client, _last_code()).status_code == 302
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_inactive_account_gets_no_code(client):
    _user(is_active=False)
    _request_reset(client)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_confirm_without_session_redirects(client):
    resp = client.get(reverse("accounts:password_reset_confirm"))
    assert resp.url == reverse("accounts:password_reset_request")


MATRICULA = "20230012345"


@pytest.mark.django_db
def test_reset_by_registration_number_sends_to_account_email_without_showing_it(client):
    user = _user()
    resp = _request_reset(client, f" {MATRICULA} ")
    assert resp.url == reverse("accounts:password_reset_confirm")
    assert mail.outbox[-1].to == [EMAIL]
    page = client.get(reverse("accounts:password_reset_confirm")).content.decode()
    assert "o e-mail cadastrado nessa matrícula" in page
    assert "a***@example.com" not in page

    assert _confirm(client, _last_code()).status_code == 302
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_unknown_registration_number_looks_the_same(client):
    _user()
    known, unknown = Client(), Client()
    resp_known = _request_reset(known, MATRICULA)
    resp_unknown = _request_reset(unknown, "99998888")
    assert resp_known.url == resp_unknown.url
    assert len(mail.outbox) == 1
    # identicas, tirando o token CSRF (aleatorio a cada request)
    def page(c):
        html = c.get(reverse("accounts:password_reset_confirm")).content.decode()
        return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", html)

    assert page(known) == page(unknown)


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["abc", "1234567", "1234567890123", "2023.0012345", "aluno@", ""])
def test_invalid_identifier_is_rejected(client, value):
    resp = _request_reset(client, value)
    assert resp.status_code == 200
    assert resp.context["form"].errors.get("identifier")
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_email_then_registration_number_share_cooldown(client):
    _user()
    _request_reset(client, EMAIL)
    _request_reset(Client(), MATRICULA)
    assert len(mail.outbox) == 1  # mesma conta -> mesmo e-mail -> cooldown de 60 s
