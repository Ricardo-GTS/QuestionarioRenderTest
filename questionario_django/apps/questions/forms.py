from django import forms


class QuestionForm(forms.Form):
    statement = forms.CharField(widget=forms.Textarea, min_length=3, label="Enunciado")
    correct_answer = forms.TypedChoiceField(
        choices=[("true", "Verdadeiro"), ("false", "Falso")],
        coerce=lambda value: value == "true",
        widget=forms.RadioSelect,
        label="Resposta correta",
    )
    category = forms.CharField(max_length=120, required=False, label="Categoria (opcional)")
