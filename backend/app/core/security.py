from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def is_admin_email(email: str) -> bool:
    return email.strip().lower() in settings.admin_emails


def verify_google_id_token(credential: str) -> dict:
    """Verifica assinatura/audience/expiracao do id_token do Google e devolve as claims.

    Levanta ValueError se o token for invalido (assinatura, audience ou expirado) --
    tratamento identico ao que a lib google-auth ja levanta internamente.
    """
    claims = google_id_token.verify_oauth2_token(
        credential, google_requests.Request(), audience=settings.google_client_id
    )
    if not claims.get("email_verified", False):
        raise ValueError("Email do Google nao verificado")
    return claims
