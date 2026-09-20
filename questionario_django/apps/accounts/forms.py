from django import forms


class RegisterForm(forms.Form):
    name = forms.CharField(max_length=120, min_length=1)
    email = forms.EmailField(max_length=255)
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
