from django.conf import settings
from django.db import models


class ReportStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    ACCEPTED = "accepted", "Aceito"
    REJECTED = "rejected", "Rejeitado"


REASON_CATEGORIES = (
    "Resposta incorreta",
    "Enunciado ambiguo ou confuso",
    "Conteudo ofensivo ou inadequado",
    "Pergunta duplicada",
    "Fora do tema",
    "Outro",
)

REASON_CATEGORY_CHOICES = [(c, c) for c in REASON_CATEGORIES]


class Report(models.Model):
    question = models.ForeignKey("questions.Question", on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    reason = models.TextField(null=True, blank=True)
    reason_category = models.CharField(max_length=60, choices=REASON_CATEGORY_CHOICES)
    status = models.CharField(max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["question", "reporter"], name="uq_reports_question_reporter"),
        ]

    def __str__(self):
        return f"Report({self.question_id}, {self.reporter_id}, {self.status})"
