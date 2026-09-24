"""Porte de backend/app/services/quiz.py."""

from apps.core.services import get_effective_settings

from .models import QuizAttempt


def pick_random_questions(exclude_author_id, size=None):
    from apps.questions.models import Question, QuestionStatus

    n = size or get_effective_settings().quiz_size
    return list(
        Question.objects.filter(status=QuestionStatus.ACTIVE)
        .exclude(author_id=exclude_author_id)
        .order_by("?")[:n]
    )


def score_quiz(questions, answers: dict[int, bool]) -> dict:
    """Pura, sem dependencia de DB. Resposta ausente conta como incorreta."""
    feedback = []
    score = 0
    for question in questions:
        given_answer = answers.get(question.id)
        is_correct = given_answer is not None and given_answer == question.correct_answer
        if is_correct:
            score += 1
        feedback.append(
            {
                "question_id": question.id,
                "statement": question.statement,
                "correct_answer": question.correct_answer,
                "given_answer": given_answer,
                "is_correct": is_correct,
            }
        )
    return {"score": score, "total": len(questions), "feedback": feedback}


def record_attempt(*, user_id, score, total) -> QuizAttempt:
    return QuizAttempt.objects.create(user_id=user_id, score=score, total=total)


QUIZ_TTL_SECONDS = 24 * 60 * 60


def current_position(question_ids: list, answers: dict, position) -> int:
    """Indice da pergunta atual. Sessoes de antes do botao "Proxima" nao tem
    quiz_position -- ai a atual e' a primeira sem resposta (como era)."""
    if position is None:
        return len(answers)
    return min(position, len(question_ids))


def quiz_expired(started_at, now_ts: float) -> bool:
    """started_at: timestamp salvo na sessao. Sem ele (sessao antiga), nao vence."""
    return started_at is not None and now_ts - started_at > QUIZ_TTL_SECONDS
