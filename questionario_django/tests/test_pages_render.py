"""Smoke test: cada pagina carrega sem erro de template/reverse."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_anonymous_pages_render(client):
    assert client.get(reverse("accounts:login")).status_code == 200
    assert client.get(reverse("accounts:register")).status_code == 200


@pytest.mark.django_db
def test_authenticated_pages_render(client):
    client.post(reverse("accounts:register"), {"name": "Fulano", "email": "fulano@example.com", "password": "senha1234", "registration_number": "20250000016"})

    assert client.get(reverse("questions:create")).status_code == 200
    assert client.get(reverse("accounts:account")).status_code == 200
    assert client.get(reverse("accounts:stats")).status_code == 200
    assert client.get(reverse("quiz:start")).status_code == 200


@pytest.mark.django_db
def test_admin_pages_render(client):
    client.post(reverse("accounts:register"), {"name": "Admin", "email": "admin@example.com", "password": "senha1234", "registration_number": "20250000017"})

    assert client.get(reverse("moderation:dashboard")).status_code == 200
    assert client.get(reverse("moderation:pending_reports")).status_code == 200
    assert client.get(reverse("moderation:removed_list")).status_code == 200
    assert client.get(reverse("moderation:admin_settings")).status_code == 200
    assert client.get(reverse("moderation:topic_list")).status_code == 200
    assert client.get(reverse("accounts:admin_user_list")).status_code == 200
