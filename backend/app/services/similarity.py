from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import QuestionStatus
from app.models.question import Question


@dataclass
class SimilarQuestion:
    question: Question
    similarity: float


def filter_by_threshold(rows: list[tuple[Question, float]], threshold: float) -> list[SimilarQuestion]:
    """Converte pares (pergunta, distancia de cosseno) em matches cuja similaridade >= threshold.

    Pura (sem DB) para facilitar teste unitario do calculo de similaridade/threshold.
    """
    max_distance = 1 - threshold
    return [
        SimilarQuestion(question=question, similarity=1 - dist)
        for question, dist in rows
        if dist <= max_distance
    ]


def find_similar_active_questions(db: Session, embedding: list[float], limit: int = 5) -> list[SimilarQuestion]:
    """Busca perguntas ativas cuja similaridade de cosseno com `embedding` >= SIMILARITY_THRESHOLD."""
    distance = Question.embedding.cosine_distance(embedding)
    stmt = (
        select(Question, distance.label("distance"))
        .where(Question.status == QuestionStatus.ACTIVE)
        .order_by(distance)
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return filter_by_threshold(rows, settings.similarity_threshold)
