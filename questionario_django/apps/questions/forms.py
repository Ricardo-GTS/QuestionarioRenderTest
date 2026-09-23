from django import forms

from . import services

NEW_TOPIC_CHOICE = "__new_topic__"


class QuestionForm(forms.Form):
    statement = forms.CharField(widget=forms.Textarea, min_length=3, label="Enunciado")
    correct_answer = forms.TypedChoiceField(
        choices=[("true", "Verdadeiro"), ("false", "Falso")],
        coerce=lambda value: value == "true",
        widget=forms.RadioSelect,
        label="Resposta correta",
    )
    topic = forms.ChoiceField(label="Tópico da questão")
    new_topic = forms.CharField(
        max_length=120,
        required=False,
        label="Novo tópico",
        help_text="Obrigatorio quando 'Novo Tópico' estiver selecionado acima.",
    )
    citations_references = forms.CharField(widget=forms.Textarea, label="Citações e referências")
    pertinence = forms.CharField(
        widget=forms.Textarea,
        label="Pertinência",
        help_text="Por que essa pergunta é relevante para uma avaliação?",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topic"].choices = [(NEW_TOPIC_CHOICE, "Novo Tópico")] + [
            (topic, topic) for topic in services.list_topic_names()
        ]

    def clean(self):
        cleaned = super().clean()
        topic = cleaned.get("topic")
        new_topic = (cleaned.get("new_topic") or "").strip()
        if topic == NEW_TOPIC_CHOICE:
            if not new_topic:
                self.add_error("new_topic", "Digite o novo tópico.")
            cleaned["topic"] = new_topic
        return cleaned
