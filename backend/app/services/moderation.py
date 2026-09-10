import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import QuestionStatus
from app.models.question import Question
from app.models.report import Report

logger = logging.getLogger(__name__)


def should_flag(report_count: int, threshold: int, current_status: QuestionStatus) -> bool:
    """Pura (sem DB) para facilitar teste unitario da regra de moderacao."""
    return report_count >= threshold and current_status == QuestionStatus.ACTIVE


def register_report(
    db: Session,
    question: Question,
    reporter_id: int,
    reason: str,
    reason_category: str | None,
) -> Report:
    report = Report(
        question_id=question.id,
        reporter_id=reporter_id,
        reason=reason,
        reason_category=reason_category,
    )
    db.add(report)
    db.flush()

    report_count = db.scalar(
        select(func.count()).select_from(Report).where(Report.question_id == question.id)
    )

    if should_flag(report_count, settings.report_threshold, question.status):
        question.status = QuestionStatus.REPORTED
        logger.info(
            "Pergunta id=%s flagada para revisao apos %s reportes (limiar=%s)",
            question.id,
            report_count,
            settings.report_threshold,
        )

    db.commit()
    db.refresh(report)
    return report
