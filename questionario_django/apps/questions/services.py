"""Porte de backend/app/services/embeddings.py + similarity.py.

Cliente Ollama sincrono (nao async) -- ver secao "Integracao com Ollama" do plano
de migracao: view Django comum, multiplos workers absorvem o paralelismo.
"""

from dataclasses import dataclass

import httpx
from django.conf import settings
from pgvector.django import CosineDistance

from apps.core.services import get_effective_settings

from .models import Question, QuestionStatus


class EmbeddingServiceError(Exception):
    pass


def get_embedding(text: str) -> list[float]:
    try:
        response = httpx.post(
            f"{settings.OLLAMA_HOST}/api/embeddings",
            json={"model": settings.OLLAMA_EMBED_MODEL, "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise EmbeddingServiceError(f"Falha ao gerar embedding: {exc}") from exc

    embedding = data.get("embedding")
    if not embedding:
        raise EmbeddingServiceError("Resposta do Ollama sem campo 'embedding'")
    return embedding


@dataclass
class SimilarQuestion:
    question: Question
    similarity: float


def filter_by_threshold(rows, threshold: float) -> list[SimilarQuestion]:
    """Pura, sem dependencia de DB -- porte literal de app/services/similarity.py."""
    max_distance = 1 - threshold
    return [
        SimilarQuestion(question=question, similarity=1 - distance)
        for question, distance in rows
        if distance <= max_distance
    ]


def find_similar_active_questions(embedding, limit: int = 5) -> list[SimilarQuestion]:
    threshold = get_effective_settings().similarity_threshold
    queryset = (
        Question.objects.filter(status=QuestionStatus.ACTIVE)
        .annotate(distance=CosineDistance("embedding", embedding))
        .order_by("distance")[:limit]
    )
    rows = [(q, q.distance) for q in queryset]
    return filter_by_threshold(rows, threshold)
