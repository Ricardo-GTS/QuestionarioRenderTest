"""Login com Google (porte de backend/app/core/security.py::verify_google_id_token) +
confirmacao de e-mail por codigo (cadastro e troca de e-mail).

Confirmacao de e-mail: o codigo (6 digitos) so' existe em texto puro no e-mail enviado;
no banco fica o HMAC-SHA256 dele. Regras de validade/tentativas/reenvio sao funcoes
puras aqui em cima; os fluxos com ORM (start_*/complete_*/resend_*) ficam embaixo.
Cooldown e limite por hora sao por e-mail de destino (EmailSendLog), nao por pendente.
"""

import hashlib
import hmac
import logging
import math
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

logger = logging.getLogger(__name__)

CODE_TTL_MINUTES = 15
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
MAX_SENDS_PER_HOUR = 5
PENDING_RETENTION_HOURS = 24

SEND_WINDOW = timedelta(hours=1)
SEND_FAILED = "Não foi possível enviar o e-mail. Tente reenviar o código em instantes."


def verify_google_id_token(credential: str) -> dict:
    request = google_requests.Request()
    payload = google_id_token.verify_oauth2_token(credential, request, settings.GOOGLE_CLIENT_ID)
    if not payload.get("email_verified", False):
        raise ValueError("Email do Google nao verificado")
    return payload


# --- Regras puras (sem banco) ---


def generate_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_code(code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def code_matches(code: str, code_hash: str) -> bool:
    return bool(code_hash) and hmac.compare_digest(hash_code(code), code_hash)


def is_code_expired(expires_at, now) -> bool:
    return expires_at is None or now >= expires_at


def seconds_until(moment, now) -> int:
    if moment is None:
        return 0
    return max(0, math.ceil((moment - now).total_seconds()))


def seconds_until_resend(last_sent_at, now) -> int:
    if last_sent_at is None:
        return 0
    return seconds_until(last_sent_at + timedelta(seconds=RESEND_COOLDOWN_SECONDS), now)


def send_quota_exceeded(sends_last_hour: int) -> bool:
    return sends_last_hour >= MAX_SENDS_PER_HOUR


def attempts_exhausted(attempts: int) -> bool:
    return attempts >= MAX_ATTEMPTS


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def normalize_code(value: str) -> str:
    """Aceita o codigo colado com espacos (ex: '123 456')."""
    return re.sub(r"\s", "", value or "")


# --- Emissao e checagem de codigo (qualquer EmailCodeBase) ---


class CodeNotSent(Exception):
    """Cooldown ou limite por hora -- a mensagem vai direto pro usuario."""


def _send_stats(email: str, now):
    """(envios na ultima hora, horario do ultimo envio) pra esse e-mail de destino."""
    from .models import EmailSendLog

    recent = EmailSendLog.objects.filter(email=email, sent_at__gte=now - SEND_WINDOW)
    return recent.count(), recent.order_by("-sent_at").values_list("sent_at", flat=True).first()


def issue_code(obj, email: str, now=None) -> str:
    """Gera um codigo novo (invalida o anterior) respeitando cooldown e limite por hora do e-mail."""
    now = now or timezone.now()
    sends_last_hour, last_sent_at = _send_stats(email, now)
    wait = seconds_until_resend(last_sent_at, now)
    if wait:
        raise CodeNotSent(f"Aguarde {wait} s para pedir um novo código.")
    if send_quota_exceeded(sends_last_hour):
        raise CodeNotSent("Limite de envios atingido. Tente novamente mais tarde.")
    code = generate_code()
    obj.code_hash = hash_code(code)
    obj.attempts = 0
    obj.code_expires_at = now + timedelta(minutes=CODE_TTL_MINUTES)
    obj.save()
    return code


@dataclass
class CodeCheck:
    status: str  # ok | invalid | expired | exhausted | missing | email_taken | registration_number_taken
    attempts_left: int = 0
    user: object = None


def _check_locked(obj, code: str, now) -> CodeCheck:
    """obj ja' travado com select_for_update pelo chamador."""
    if attempts_exhausted(obj.attempts):
        return CodeCheck("exhausted")
    if is_code_expired(obj.code_expires_at, now):
        return CodeCheck("expired")
    if code_matches(code, obj.code_hash):
        return CodeCheck("ok")
    obj.attempts += 1
    obj.save(update_fields=["attempts"])
    if attempts_exhausted(obj.attempts):
        return CodeCheck("exhausted")
    return CodeCheck("invalid", attempts_left=MAX_ATTEMPTS - obj.attempts)


def _send_new_code(obj, email: str, now=None) -> str | None:
    """Gera e envia um codigo novo. Devolve a mensagem de erro pro usuario, ou None se enviou."""
    from .models import EmailSendLog

    now = now or timezone.now()
    try:
        code = issue_code(obj, email, now)
    except CodeNotSent as exc:
        return str(exc)
    if not send_code_email(email, code):
        # Nada saiu -- sem EmailSendLog, o reenvio fica liberado na hora.
        return SEND_FAILED
    EmailSendLog.objects.create(email=email, sent_at=now)
    return None


def code_timers(obj, email: str, now=None) -> dict:
    """Segundos restantes pra expirar o codigo e pra liberar o reenvio (contagem regressiva na tela)."""
    now = now or timezone.now()
    _, last_sent_at = _send_stats(email, now)
    return {
        "expires_in": seconds_until(obj.code_expires_at, now),
        "resend_in": seconds_until_resend(last_sent_at, now),
    }


# --- E-mails ---


def send_code_email(email: str, code: str) -> bool:
    context = {"code": code, "ttl_minutes": CODE_TTL_MINUTES}
    try:
        send_mail(
            subject="Seu código de confirmação – Questionario",
            message=render_to_string("accounts/email/code.txt", context),
            html_message=render_to_string("accounts/email/code.html", context),
            from_email=None,
            recipient_list=[email],
        )
    except Exception:
        # Nunca logar o codigo.
        logger.exception("Falha ao enviar codigo de confirmacao para %s", mask_email(email))
        return False
    return True


def send_email_changed_notice(old_email: str, new_email: str) -> None:
    context = {"new_email_masked": mask_email(new_email)}
    try:
        send_mail(
            subject="O e-mail da sua conta foi alterado – Questionario",
            message=render_to_string("accounts/email/email_changed.txt", context),
            from_email=None,
            recipient_list=[old_email],
        )
    except Exception:
        logger.exception("Falha ao avisar troca de e-mail para %s", mask_email(old_email))


# --- Cadastro pendente ---


def start_registration(
    *, session_pending_id, name: str, email: str, registration_number: str, password: str, now=None
):
    """Cria o cadastro pendente desta sessao (ou atualiza o que ela ja tem) e envia o codigo.
    Nunca reaproveita pendente de outra sessao, mesmo com o mesmo e-mail -- ver
    PendingRegistration. Devolve (pending, mensagem_de_erro_ou_None)."""
    from django.contrib.auth.hashers import make_password

    from .models import EmailSendLog, PendingRegistration

    now = now or timezone.now()
    cutoff = now - timedelta(hours=PENDING_RETENTION_HOURS)
    PendingRegistration.objects.filter(created_at__lt=cutoff).delete()
    EmailSendLog.objects.filter(sent_at__lt=cutoff).delete()

    pending = None
    if session_pending_id is not None:
        pending = PendingRegistration.objects.filter(pk=session_pending_id).first()
    if pending is None:
        pending = PendingRegistration(email=email)
    elif pending.email != email:
        # Trocou o e-mail ("Usar outro e-mail"): o codigo mandado pro e-mail anterior deixa de valer.
        pending.email = email
        pending.code_hash = ""
        pending.attempts = 0
        pending.code_expires_at = None
    pending.name = name
    pending.registration_number = registration_number
    pending.password_hash = make_password(password)
    pending.save()
    return pending, _send_new_code(pending, email, now)


def resend_registration_code(pending) -> str | None:
    return _send_new_code(pending, pending.email)


@transaction.atomic
def complete_registration(pending_id: int, code: str, now=None) -> CodeCheck:
    """Confere o codigo e, se certo, cria o User (checando de novo e-mail/matricula livres)."""
    from .models import PendingRegistration, User

    now = now or timezone.now()
    pending = PendingRegistration.objects.select_for_update().filter(pk=pending_id).first()
    if pending is None:
        return CodeCheck("missing")
    result = _check_locked(pending, normalize_code(code), now)
    if result.status != "ok":
        return result
    if User.objects.filter(email__iexact=pending.email).exists():
        pending.delete()
        return CodeCheck("email_taken")
    if User.objects.filter(registration_number=pending.registration_number).exists():
        pending.delete()
        return CodeCheck("registration_number_taken")
    user = User(email=pending.email, name=pending.name, registration_number=pending.registration_number)
    user.password = pending.password_hash
    user.save()
    pending.delete()
    return CodeCheck("ok", user=user)


# --- Troca de e-mail ---


def start_email_change(user, new_email: str, now=None):
    """Cria/atualiza a troca pendente e envia o codigo ao NOVO e-mail. user.email nao muda
    aqui. Devolve (request, mensagem_de_erro_ou_None)."""
    from .models import EmailChangeRequest

    req, _ = EmailChangeRequest.objects.get_or_create(user=user, defaults={"new_email": new_email})
    if req.new_email != new_email:
        req.new_email = new_email
        req.save(update_fields=["new_email"])
    return req, _send_new_code(req, new_email, now)


def resend_email_change_code(req) -> str | None:
    return _send_new_code(req, req.new_email)


@transaction.atomic
def complete_email_change(user, code: str, now=None) -> CodeCheck:
    from .models import EmailChangeRequest, User

    now = now or timezone.now()
    req = EmailChangeRequest.objects.select_for_update().filter(user=user).first()
    if req is None:
        return CodeCheck("missing")
    result = _check_locked(req, normalize_code(code), now)
    if result.status != "ok":
        return result
    if User.objects.filter(email__iexact=req.new_email).exclude(pk=user.pk).exists():
        req.delete()
        return CodeCheck("email_taken")
    old_email = user.email
    user.email = req.new_email
    user.save(update_fields=["email"])
    req.delete()
    transaction.on_commit(lambda: send_email_changed_notice(old_email, user.email))
    return CodeCheck("ok", user=user)
