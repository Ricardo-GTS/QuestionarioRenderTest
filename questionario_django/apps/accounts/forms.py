import re

from django import forms

from . import services
from .models import REGISTRATION_NUMBER_VALIDATOR


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
