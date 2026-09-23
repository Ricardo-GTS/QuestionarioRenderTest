import re

from django import forms

from django.core.validators import validate_email

from . import services
from .models import REGISTRATION_NUMBER_VALIDATOR

IDENTIFIER_ERROR = "Informe um e-mail válido ou a matrícula (8 a 12 números)."


def registration_number_field():
    return forms.CharField(
        min_length=8,
        max_length=12,
        label="Matrícula da Universidade",
        validators=[REGISTRATION_NUMBER_VALIDATOR],
    )


class RegisterForm(forms.Form):
    name = forms.CharField(max_length=120, min_length=1)
    email = forms.EmailField(max_length=255)
    registration_number = registration_number_field()
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, max_length=72)


class LoginForm(forms.Form):
    email = forms.EmailField(max_length=255)
    password = forms.CharField(widget=forms.PasswordInput)


class AccountForm(forms.Form):
    name = forms.CharField(max_length=120, min_length=1)
    email = forms.EmailField(max_length=255)
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        min_length=8,
        max_length=72,
        help_text="Deixe em branco para manter a senha atual.",
    )

    def __init__(self, *args, reauthenticated=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Sem o codigo de "confirmar que e' voce", e-mail e senha ficam travados: campo
        # disabled ignora o que vier no POST e usa o valor inicial (garantido no servidor).
        if not reauthenticated:
            self.fields["email"].disabled = True
            self.fields["password"].disabled = True


class RegistrationNumberForm(forms.Form):
    registration_number = registration_number_field()


class EmailCodeForm(forms.Form):
    code = forms.CharField(
        max_length=20,
        label="Código de confirmação",
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "autofocus": True, "placeholder": "000000"}
        ),
    )

    def clean_code(self):
        code = services.normalize_code(self.cleaned_data["code"])
        if not re.fullmatch(r"\d{6}", code):
            raise forms.ValidationError("O código tem 6 números.")
        return code


class ForgotPasswordForm(forms.Form):
    identifier = forms.CharField(max_length=255, label="E-mail ou matrícula")

    def clean_identifier(self):
        """Devolve ("registration_number", valor) ou ("email", valor em minusculas)."""
        value = self.cleaned_data["identifier"].strip()
        if value.isdigit():
            try:
                REGISTRATION_NUMBER_VALIDATOR(value)
            except forms.ValidationError:
                raise forms.ValidationError(IDENTIFIER_ERROR)
            return ("registration_number", value)
        try:
            validate_email(value)
        except forms.ValidationError:
            raise forms.ValidationError(IDENTIFIER_ERROR)
        return ("email", value.lower())


class ResetPasswordForm(EmailCodeForm):
    new_password = forms.CharField(widget=forms.PasswordInput, min_length=8, max_length=72, label="Nova senha")
    new_password_confirm = forms.CharField(widget=forms.PasswordInput, label="Repita a nova senha")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_password") and cleaned.get("new_password") != cleaned.get("new_password_confirm"):
            self.add_error("new_password_confirm", "As senhas não conferem.")
        return cleaned
