"""Confirmacao de e-mail por codigo: a conta so' e' criada depois do codigo certo;
troca de e-mail na Conta so' vale depois do codigo enviado ao novo e-mail."""

import re
from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import EmailChangeRequest, EmailSendLog, PendingRegistration, User
from conftest import register_user

REGISTER = {"name": "Aluno", "email": "aluno@example.com", "password": "senha1234", "registration_number": "20230012345"}
NOW = timezone.now()


def _last_code(email):
    message = next(m for m in reversed(mail.outbox) if email in m.to)
    return re.search(r"\b(\d{6})\b", message.body).group(1)


def _wrong(code):
    return f"{(int(code) + 1) % 10**6:06d}"


def _pass_cooldown():
    """Empurra os envios registrados pra tras o suficiente pra liberar o reenvio (mas
    ainda dentro da janela de 1h do limite por hora)."""
    for log in EmailSendLog.objects.all():
        log.sent_at -= timedelta(seconds=services.RESEND_COOLDOWN_SECONDS + 1)
        log.save(update_fields=["sent_at"])


# --- Regras puras ---


def test_generate_code_has_6_digits():
    for _ in range(50):
        assert re.fullmatch(r"\d{6}", services.generate_code())


def test_code_hash_matches_only_same_code():
    code_hash = services.hash_code("123456")
    assert code_hash != "123456"
    assert services.code_matches("123456", code_hash)
    assert not services.code_matches("654321", code_hash)
    assert not services.code_matches("123456", "")


def test_expiry_and_resend_cooldown():
    assert services.is_code_expired(None, NOW)
    assert services.is_code_expired(NOW, NOW)
    assert not services.is_code_expired(NOW + timedelta(seconds=1), NOW)
    assert services.seconds_until_resend(None, NOW) == 0
    assert services.seconds_until_resend(NOW, NOW) == services.RESEND_COOLDOWN_SECONDS
    assert services.seconds_until_resend(NOW - timedelta(seconds=services.RESEND_COOLDOWN_SECONDS), NOW) == 0


def test_send_quota_per_hour():
    assert not services.send_quota_exceeded(services.MAX_SENDS_PER_HOUR - 1)
    assert services.send_quota_exceeded(services.MAX_SENDS_PER_HOUR)


def test_attempts_mask_and_normalize():
    assert not services.attempts_exhausted(services.MAX_ATTEMPTS - 1)
    assert services.attempts_exhausted(services.MAX_ATTEMPTS)
    assert services.mask_email("aluno@gmail.com") == "a***@gmail.com"
    assert services.normalize_code(" 123 456 ") == "123456"


# --- Cadastro ---


@pytest.mark.django_db
def test_register_does_not_create_user_until_code_confirmed(client):
    resp = client.post(reverse("accounts:register"), REGISTER)
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:confirm_registration")
    assert not User.objects.filter(email=REGISTER["email"]).exists()
    assert len(mail.outbox) == 1
    code = _last_code(REGISTER["email"])
    pending = PendingRegistration.objects.get(email=REGISTER["email"])
    assert code not in pending.code_hash
    assert pending.password_hash != REGISTER["password"]

    page = client.get(reverse("accounts:confirm_registration"))
    assert page.status_code == 200
    assert "a***@example.com" in page.content.decode()

    resp = client.post(reverse("accounts:confirm_registration"), {"code": f"{code[:3]} {code[3:]}"})
    assert resp.status_code == 302
    user = User.objects.get(email=REGISTER["email"])
    assert user.registration_number == REGISTER["registration_number"]
    assert user.check_password(REGISTER["password"])
    assert not PendingRegistration.objects.exists()
    # logado e com acesso liberado
    assert client.get(reverse("questions:create")).status_code == 200


@pytest.mark.django_db
def test_wrong_code_counts_attempts_until_exhausted(client):
    client.post(reverse("accounts:register"), REGISTER)
    code = _last_code(REGISTER["email"])
    url = reverse("accounts:confirm_registration")

    resp = client.post(url, {"code": _wrong(code)})
    assert "Restam 4" in resp.context["form"].errors["code"][0]
    for _ in range(services.MAX_ATTEMPTS - 1):
        resp = client.post(url, {"code": _wrong(code)})
    assert "Muitas tentativas" in resp.context["form"].errors["code"][0]
    # esgotado: nem o codigo certo passa mais
    resp = client.post(url, {"code": code})
    assert resp.status_code == 200
    assert not User.objects.filter(email=REGISTER["email"]).exists()


@pytest.mark.django_db
def test_expired_code_is_rejected(client):
    client.post(reverse("accounts:register"), REGISTER)
    code = _last_code(REGISTER["email"])
    PendingRegistration.objects.update(code_expires_at=timezone.now() - timedelta(seconds=1))
    resp = client.post(reverse("accounts:confirm_registration"), {"code": code})
    assert "expirado" in resp.context["form"].errors["code"][0]
    assert not User.objects.exists()


@pytest.mark.django_db
def test_resend_respects_cooldown_replaces_code_and_hourly_limit(client):
    client.post(reverse("accounts:register"), REGISTER)
    first_code = _last_code(REGISTER["email"])
    resend = reverse("accounts:resend_registration_code")

    client.post(resend)  # antes dos 60s -> nao envia
    assert len(mail.outbox) == 1

    _pass_cooldown()
    client.post(resend)
    assert len(mail.outbox) == 2
    new_code = _last_code(REGISTER["email"])
    # codigo antigo deixa de valer
    if new_code != first_code:
        resp = client.post(reverse("accounts:confirm_registration"), {"code": first_code})
        assert resp.status_code == 200

    for _ in range(services.MAX_SENDS_PER_HOUR - 2):
        _pass_cooldown()
        client.post(resend)
    assert len(mail.outbox) == services.MAX_SENDS_PER_HOUR
    _pass_cooldown()
    client.post(resend)  # 6o envio na mesma hora -> bloqueado
    assert len(mail.outbox) == services.MAX_SENDS_PER_HOUR

    # refazer o cadastro (mesma sessao ou outra) nao escapa do limite: e' por e-mail
    client.post(reverse("accounts:register"), REGISTER)
    type(client)().post(reverse("accounts:register"), REGISTER)
    assert len(mail.outbox) == services.MAX_SENDS_PER_HOUR


@pytest.mark.django_db
def test_confirm_page_shows_timers(client):
    client.post(reverse("accounts:register"), REGISTER)
    resp = client.get(reverse("accounts:confirm_registration"))
    assert 0 < resp.context["expires_in"] <= services.CODE_TTL_MINUTES * 60
    assert 0 < resp.context["resend_in"] <= services.RESEND_COOLDOWN_SECONDS
    assert "disabled" in resp.content.decode()


@pytest.mark.django_db
def test_email_or_registration_number_taken_while_pending(client):
    client.post(reverse("accounts:register"), REGISTER)
    code = _last_code(REGISTER["email"])
    User.objects.create_user(
        email="outro@example.com", name="Outro", password="senha1234", registration_number=REGISTER["registration_number"]
    )
    resp = client.post(reverse("accounts:confirm_registration"), {"code": code})
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:register")
    assert not User.objects.filter(email=REGISTER["email"]).exists()
    assert not PendingRegistration.objects.exists()


@pytest.mark.django_db
def test_other_session_cannot_overwrite_pending_password(client):
    """Ataque: alguem se cadastra com o e-mail da vitima (que esta com cadastro pendente)
    usando a propria senha. O codigo que a vitima recebe tem que criar a conta com a
    senha DELA, nunca com a do atacante."""
    client.post(reverse("accounts:register"), REGISTER)
    victim_code = _last_code(REGISTER["email"])

    attacker = type(client)()
    attacker.post(reverse("accounts:register"), {**REGISTER, "password": "senhadoatacante", "registration_number": "99990000"})
    assert PendingRegistration.objects.count() == 2

    resp = client.post(reverse("accounts:confirm_registration"), {"code": victim_code})
    assert resp.status_code == 302
    user = User.objects.get(email=REGISTER["email"])
    assert user.check_password(REGISTER["password"])
    assert not user.check_password("senhadoatacante")
    assert user.registration_number == REGISTER["registration_number"]
    # e o codigo da vitima nao serve pro pendente do atacante
    assert attacker.post(reverse("accounts:confirm_registration"), {"code": victim_code}).status_code == 200


@pytest.mark.django_db
def test_changing_email_in_same_session_invalidates_old_code(client):
    client.post(reverse("accounts:register"), REGISTER)
    old_code = _last_code(REGISTER["email"])
    client.post(reverse("accounts:register"), {**REGISTER, "email": "correto@example.com"})
    assert PendingRegistration.objects.count() == 1
    resp = client.post(reverse("accounts:confirm_registration"), {"code": old_code})
    assert resp.status_code == 200
    new_code = _last_code("correto@example.com")
    assert client.post(reverse("accounts:confirm_registration"), {"code": new_code}).status_code == 302
    assert User.objects.filter(email="correto@example.com").exists()


@pytest.mark.django_db
def test_smtp_failure_keeps_pending_and_allows_immediate_resend(client):
    with mock.patch("apps.accounts.services.send_mail", side_effect=OSError("smtp down")):
        resp = client.post(reverse("accounts:register"), REGISTER, follow=True)
    assert "Não foi possível enviar" in resp.content.decode()
    assert PendingRegistration.objects.count() == 1
    assert not EmailSendLog.objects.exists()
    client.post(reverse("accounts:resend_registration_code"))
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_confirm_without_pending_redirects_to_register(client):
    resp = client.get(reverse("accounts:confirm_registration"))
    assert resp.status_code == 302
    assert resp.url == reverse("accounts:register")


# --- Login com Google ---


@pytest.mark.django_db
def test_google_login_rejects_unverified_email(client, settings):
    settings.GOOGLE_CLIENT_ID = "client-id"
    payload = {"sub": "123", "email": "g@example.com", "email_verified": False}
    with mock.patch("apps.accounts.services.google_id_token.verify_oauth2_token", return_value=payload):
        resp = client.post(reverse("accounts:google_login"), {"credential": "x"})
    assert resp.url == reverse("accounts:login")
    assert not User.objects.filter(email="g@example.com").exists()


# --- Troca de e-mail ---


def _logged_user(client):
    register_user(client, REGISTER)
    mail.outbox.clear()
    return User.objects.get(email=REGISTER["email"])


@pytest.mark.django_db
def test_email_change_only_applies_after_code(client, django_capture_on_commit_callbacks):
    user = _logged_user(client)
    resp = client.post(
        reverse("accounts:account"), {"name": "Aluno Novo", "email": "novo@example.com", "password": ""}
    )
    assert resp.url == reverse("accounts:confirm_email_change")
    user.refresh_from_db()
    assert user.email == REGISTER["email"]
    assert user.name == "Aluno Novo"
    assert mail.outbox[-1].to == ["novo@example.com"]
    code = _last_code("novo@example.com")
    assert "n***@example.com" in client.get(reverse("accounts:account")).content.decode()

    resp = client.post(reverse("accounts:confirm_email_change"), {"code": _wrong(code)})
    assert resp.status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse("accounts:confirm_email_change"), {"code": code})
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.email == "novo@example.com"
    assert not EmailChangeRequest.objects.exists()
    # aviso pro e-mail antigo
    assert any(m.to == [REGISTER["email"]] and "alterado" in m.subject for m in mail.outbox)


@pytest.mark.django_db
def test_email_change_cancel_and_conflict(client):
    user = _logged_user(client)
    client.post(reverse("accounts:account"), {"name": "Aluno", "email": "novo@example.com", "password": ""})
    client.post(reverse("accounts:cancel_email_change"))
    assert not EmailChangeRequest.objects.exists()
    assert client.get(reverse("accounts:confirm_email_change")).url == reverse("accounts:account")

    _pass_cooldown()
    client.post(reverse("accounts:account"), {"name": "Aluno", "email": "novo@example.com", "password": ""})
    code = _last_code("novo@example.com")
    User.objects.create_user(email="novo@example.com", name="Outro", password="senha1234", registration_number="55556666")
    resp = client.post(reverse("accounts:confirm_email_change"), {"code": code})
    assert resp.url == reverse("accounts:account")
    user.refresh_from_db()
    assert user.email == REGISTER["email"]
    assert not EmailChangeRequest.objects.exists()


@pytest.mark.django_db
def test_email_change_resend_cooldown(client):
    _logged_user(client)
    client.post(reverse("accounts:account"), {"name": "Aluno", "email": "novo@example.com", "password": ""})
    client.post(reverse("accounts:resend_email_change_code"))
    assert len(mail.outbox) == 1
    _pass_cooldown()
    client.post(reverse("accounts:resend_email_change_code"))
    assert len(mail.outbox) == 2
