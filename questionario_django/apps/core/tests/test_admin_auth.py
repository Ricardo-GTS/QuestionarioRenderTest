"""Porte de backend/tests/test_admin_auth.py."""

from django.test import override_settings

from apps.core.permissions import is_admin_email


@override_settings(ADMIN_EMAILS={"admin@example.com"})
def test_is_admin_email_case_insensitive():
    assert is_admin_email("ADMIN@example.com") is True


@override_settings(ADMIN_EMAILS={"admin@example.com"})
def test_is_admin_email_outside_list():
    assert is_admin_email("aluno@example.com") is False
