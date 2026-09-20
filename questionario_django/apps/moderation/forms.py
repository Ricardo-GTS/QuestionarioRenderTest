from django import forms

from .models import REASON_CATEGORY_CHOICES


class ReportForm(forms.Form):
    reason_category = forms.ChoiceField(choices=REASON_CATEGORY_CHOICES, label="Tipo de problema")
    reason = forms.CharField(
        widget=forms.Textarea,
        required=False,
        min_length=3,
        label="Motivo",
        help_text="Obrigatorio quando o tipo de problema for 'Outro'.",
    )

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("reason_category")
        reason = (cleaned.get("reason") or "").strip()
        if category == "Outro" and not reason:
            self.add_error("reason", "Descreva o motivo quando o tipo de problema for 'Outro'")
        return cleaned


class QuestionEditForm(forms.Form):
    statement = forms.CharField(widget=forms.Textarea, min_length=3, label="Enunciado")
    correct_answer = forms.TypedChoiceField(
        choices=[("true", "Verdadeiro"), ("false", "Falso")],
        coerce=lambda value: value == "true",
        widget=forms.RadioSelect,
        label="Resposta correta",
    )
    category = forms.CharField(max_length=120, required=False, label="Categoria (opcional)")


class AppSettingsForm(forms.Form):
    similarity_threshold = forms.FloatField(min_value=0.01, max_value=1.0, label="Limiar de similaridade")
    quiz_size = forms.IntegerField(min_value=1, label="Tamanho do questionario")
    report_threshold = forms.IntegerField(min_value=1, label="Limiar de reportes")
