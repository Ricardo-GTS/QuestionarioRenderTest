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
    category = models.CharField(max_length=120, null=True, blank=True)
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
