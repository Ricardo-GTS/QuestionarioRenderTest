"""Porte de backend/app/core/security.py::verify_google_id_token."""

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token


def verify_google_id_token(credential: str) -> dict:
    request = google_requests.Request()
    payload = google_id_token.verify_oauth2_token(credential, request, settings.GOOGLE_CLIENT_ID)
    if not payload.get("email_verified", False):
        raise ValueError("Email do Google nao verificado")
    return payload
