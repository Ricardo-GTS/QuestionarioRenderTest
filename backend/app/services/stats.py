from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import QuestionStatus
from app.models.question import Question
from app.models.quiz_attempt import QuizAttempt
from app.models.report import Report
from app.models.user import User

NO_CATEGORY_LABEL = "Sem categoria"


def compute_average_score_percent(attempts: list[tuple[int, int]]) -> float | None:
    """Pura (sem DB) para facilitar teste unitario do calculo do dashboard."""
    percentages = [score / total for score, total in attempts if total > 0]
    if not percentages:
        return None
    return (sum(percentages) / len(percentages)) * 100


def compute_stats(db: Session) -> dict:
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    total_reports = db.scalar(select(func.count()).select_from(Report)) or 0

    status_counts = dict(db.execute(select(Question.status, func.count()).group_by(Question.status)).all())

    attempts = db.execute(select(QuizAttempt.score, QuizAttempt.total)).all()
    average_score_percent = compute_average_score_percent([(score, total) for score, total in attempts])

    category_column = func.coalesce(Question.category, NO_CATEGORY_LABEL)
    questions_by_category = db.execute(select(category_column, func.count()).group_by(category_column)).all()
    reports_by_category = db.execute(
        select(category_column, func.count(Report.id))
        .join(Report, Report.question_id == Question.id)
        .group_by(category_column)
    ).all()

    return {
        "total_users": total_users,
        "total_questions_active": status_counts.get(QuestionStatus.ACTIVE, 0),
        "total_questions_reported": status_counts.get(QuestionStatus.REPORTED, 0),
        "total_questions_removed": status_counts.get(QuestionStatus.REMOVED, 0),
        "total_reports": total_reports,
        "total_quiz_attempts": len(attempts),
        "average_score_percent": average_score_percent,
        "questions_by_category": [{"category": c, "count": n} for c, n in questions_by_category],
        "reports_by_category": [{"category": c, "count": n} for c, n in reports_by_category],
    }
