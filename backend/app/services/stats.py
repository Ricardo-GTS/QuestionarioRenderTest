from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import QuestionStatus, ReportStatus
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


def compute_user_reputation(db: Session, user_id: int) -> dict:
    """Reputacao de UM usuario -- calculada na hora a partir de reports/questions
    existentes, sem contador denormalizado (ver decisao registrada na memoria
    do projeto/CLAUDE.md sobre o sistema de reportes)."""
    accepted_reports = db.scalar(
        select(func.count())
        .select_from(Report)
        .where(Report.reporter_id == user_id, Report.status == ReportStatus.ACCEPTED)
    ) or 0
    rejected_reports = db.scalar(
        select(func.count())
        .select_from(Report)
        .where(Report.reporter_id == user_id, Report.status == ReportStatus.REJECTED)
    ) or 0
    questions_removed = db.scalar(
        select(func.count())
        .select_from(Question)
        .where(Question.author_id == user_id, Question.status == QuestionStatus.REMOVED)
    ) or 0
    return {
        "accepted_reports_count": accepted_reports,
        "rejected_reports_count": rejected_reports,
        "questions_removed_count": questions_removed,
    }


def compute_all_users_reputation(db: Session) -> dict[int, dict]:
    """Mesma coisa que compute_user_reputation, mas pra todos os usuarios de uma
    vez (3 queries agregadas em vez de N+1) -- usado na listagem do admin."""
    accepted_by_user = dict(
        db.execute(
            select(Report.reporter_id, func.count())
            .where(Report.status == ReportStatus.ACCEPTED)
            .group_by(Report.reporter_id)
        ).all()
    )
    rejected_by_user = dict(
        db.execute(
            select(Report.reporter_id, func.count())
            .where(Report.status == ReportStatus.REJECTED)
            .group_by(Report.reporter_id)
        ).all()
    )
    removed_by_author = dict(
        db.execute(
            select(Question.author_id, func.count())
            .where(Question.status == QuestionStatus.REMOVED)
            .group_by(Question.author_id)
        ).all()
    )
    user_ids = set(accepted_by_user) | set(rejected_by_user) | set(removed_by_author)
    return {
        user_id: {
            "accepted_reports_count": accepted_by_user.get(user_id, 0),
            "rejected_reports_count": rejected_by_user.get(user_id, 0),
            "questions_removed_count": removed_by_author.get(user_id, 0),
        }
        for user_id in user_ids
    }


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
