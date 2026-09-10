from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import QuestionStatus
from app.models.question import Question


def pick_random_questions(db: Session, exclude_author_id: int, size: int | None = None) -> list[Question]:
    """Seleciona `size` perguntas ativas aleatorias, excluindo as do proprio usuario."""
    limit = size or settings.quiz_size
    stmt = (
        select(Question)
        .where(Question.status == QuestionStatus.ACTIVE, Question.author_id != exclude_author_id)
        .order_by(func.random())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def score_quiz(questions: list[Question], answers: dict[int, bool]) -> dict:
    """Calcula pontuacao e feedback por pergunta a partir das respostas do usuario."""
    feedback = []
    correct_count = 0
    for question in questions:
        given_answer = answers.get(question.id)
        is_correct = given_answer is not None and given_answer == question.correct_answer
        if is_correct:
            correct_count += 1
        feedback.append(
            {
                "question_id": question.id,
                "statement": question.statement,
                "correct_answer": question.correct_answer,
                "given_answer": given_answer,
                "is_correct": is_correct,
            }
        )

    return {
        "score": correct_count,
        "total": len(questions),
        "feedback": feedback,
    }
