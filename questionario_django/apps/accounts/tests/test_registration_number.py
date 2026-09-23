"""Matricula da Universidade: obrigatoria no cadastro, unica, 8-12 digitos, e
pedida no 1o acesso de contas sem matricula (login com Google / contas antigas)."""

import pytest
from django.urls import reverse

from apps.accounts.models import User

REGISTER = {"name": "Aluno", "email": "aluno@example.com", "password": "senha1234"}


@pytest.mark.django_db
def test_register_saves_registration_number(client):
    resp = client.post(reverse("accounts:register"), {**REGISTER, "registration_number": "20230012345"})
    assert resp.status_code == 302
    assert User.objects.get(email="aluno@example.com").registration_number == "20230012345"


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["", "1234567", "1234567890123", "2023001234a", "2023.001234"])
def test_register_rejects_invalid_registration_number(client, value):
    resp = client.post(reverse("accounts:register"), {**REGISTER, "registration_number": value})
    assert resp.status_code == 200
    assert resp.context["form"].errors.get("registration_number")
    assert not User.objects.filter(email="aluno@example.com").exists()


@pytest.mark.django_db
def test_register_accepts_8_and_12_digits(client):
    assert client.post(reverse("accounts:register"), {**REGISTER, "registration_number": "12345678"}).status_code == 302
    client.post(reverse("accounts:logout"))
    resp = client.post(
        reverse("accounts:register"),
        {**REGISTER, "email": "outro@example.com", "registration_number": "123456789012"},
    )
    assert resp.status_code == 302


@pytest.mark.django_db
def test_register_rejects_duplicate_registration_number(client):
    User.objects.create_user(email="dono@example.com", name="Dono", password="senha1234", registration_number="20230012345")
    resp = client.post(reverse("accounts:register"), {**REGISTER, "registration_number": "20230012345"})
    assert resp.status_code == 200
    assert resp.context["form"].errors.get("registration_number")


@pytest.mark.django_db
def test_user_without_registration_number_is_sent_to_complete_page(client):
    User.objects.create_user(email="antigo@example.com", name="Antigo", password="senha1234")
    client.login(username="antigo@example.com", password="senha1234")
    target = reverse("accounts:complete_registration_number")

    resp = client.get(reverse("questions:create"))
    assert resp.status_code == 302
    assert resp.url == target
    # HTMX recebe HX-Redirect em vez de um 302 que trocaria so' um pedaco da tela
    resp = client.get(reverse("quiz:start"), HTTP_HX_REQUEST="true")
    assert resp["HX-Redirect"] == target
    # tela de completar, health e logout continuam acessiveis
    assert client.get(target).status_code == 200
    assert client.get(reverse("core:health")).status_code in (200, 503)

    User.objects.create_user(email="dono@example.com", name="Dono", password="senha1234", registration_number="11112222")
    resp = client.post(target, {"registration_number": "11112222"})
    assert resp.status_code == 200
    assert resp.context["form"].errors.get("registration_number")

    resp = client.post(target, {"registration_number": "20230012345"})
    assert resp.status_code == 302
    assert User.objects.get(email="antigo@example.com").registration_number == "20230012345"
    assert client.get(reverse("questions:create")).status_code == 200


@pytest.mark.django_db
def test_account_page_edits_registration_number(client):
    client.post(reverse("accounts:register"), {**REGISTER, "registration_number": "20230012345"})
    resp = client.post(
        reverse("accounts:account"),
        {"name": "Aluno", "email": "aluno@example.com", "registration_number": "20239999999", "password": ""},
    )
    assert resp.status_code == 302
    assert User.objects.get(email="aluno@example.com").registration_number == "20239999999"
