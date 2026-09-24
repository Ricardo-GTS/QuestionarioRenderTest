from django import forms

from . import services

NEW_TOPIC_CHOICE = "__new_topic__"


class QuestionForm(forms.Form):
    statement = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Ex.: No Scrum, o Product Owner prioriza o backlog do produto."}),
        min_length=3,
        label="Enunciado",
    )
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
        help_text="Obrigatório quando “Novo tópico” estiver selecionado acima.",
    )
    citations_references = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Citações e referências")
    pertinence = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Pertinência",
        help_text="Por que essa pergunta é relevante para uma avaliação?",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topic"].choices = [(NEW_TOPIC_CHOICE, "Novo tópico")] + [
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


class CommentForm(forms.Form):
    text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 1000, "placeholder": "Deixe um comentário"}),
        min_length=1,
        max_length=1000,
        label="Comentário",
        strip=True,
    )


class CommentReportForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 500}),
        min_length=3,
        max_length=500,
        strip=True,
        label="Motivo",
        help_text="Explique o problema do comentário (obrigatório).",
    )
