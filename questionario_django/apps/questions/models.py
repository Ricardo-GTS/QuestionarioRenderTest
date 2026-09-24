from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

EMBEDDING_DIM = 1024  # bge-m3


class QuestionStatus(models.TextChoices):
    ACTIVE = "active", "Ativa"
    REPORTED = "reported", "Reportada"
    REMOVED = "removed", "Removida"


class Question(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="questions")
    statement = models.TextField()
    correct_answer = models.BooleanField()
    topic = models.CharField(max_length=120)
    citations_references = models.TextField()
    pertinence = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIM)
    status = models.CharField(max_length=20, choices=QuestionStatus.choices, default=QuestionStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"], name="ix_questions_status"),
            HnswIndex(
                name="ix_questions_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return self.statement[:60]


class Topic(models.Model):
    """Catalogo de topicos gerenciado pelo admin. Question.topic continua sendo
    texto (nao FK): o select de topicos e' a uniao deste catalogo com os topicos
    ja usados em perguntas -- ver questions.services.list_topic_names. Esta tabela
    so' precisa guardar topicos criados pelo admin que ainda nao tem pergunta."""

    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class QuestionComment(models.Model):
    """Comentario de aluno numa questao. Visivel so' pra quem respondeu a questao no
    quiz atual, pra quem ja' comentou nela, ou admin (services.can_view_comments).
    removed=True: ocultado pelo admin (fica guardado pra historico dos reportes)."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="question_comments")
    text = models.TextField()
    removed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["question", "removed"], name="ix_comment_question_removed")]

    def __str__(self):
        return self.text[:60]


class CommentReportStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    ACCEPTED = "accepted", "Aceito"
    REJECTED = "rejected", "Rejeitado"


COMMENT_REPORT_CATEGORIES = (
    "Ofensivo ou inadequado",
    "Entrega a resposta",
    "Spam ou fora do tema",
    "Outro",
)
COMMENT_REPORT_CATEGORY_CHOICES = [(c, c) for c in COMMENT_REPORT_CATEGORIES]


class CommentReport(models.Model):
    comment = models.ForeignKey(QuestionComment, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_reports")
    reason_category = models.CharField(max_length=60, choices=COMMENT_REPORT_CATEGORY_CHOICES)
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=CommentReportStatus.choices, default=CommentReportStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["comment", "reporter"], name="uq_comment_reports_comment_reporter"),
        ]


class CommentSeen(models.Model):
    """Ultima vez que o usuario abriu os comentarios da questao -- base do selo "N novos"."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments_seen")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="comments_seen")
    last_seen_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "question"], name="uq_comment_seen_user_question"),
        ]
