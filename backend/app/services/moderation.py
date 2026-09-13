import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import QuestionStatus, ReportStatus
from app.models.question import Question
from app.models.report import Report
from app.services.embeddings import get_embedding
from app.services.runtime_settings import get_effective_settings

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

    report_threshold = get_effective_settings(db).report_threshold
    if should_flag(report_count, report_threshold, question.status):
        question.status = QuestionStatus.REPORTED
        logger.info(
            "Pergunta id=%s flagada para revisao apos %s reportes (limiar=%s)",
            question.id,
            report_count,
            report_threshold,
        )

    db.commit()
    db.refresh(report)
    return report


def list_questions_by_status(db: Session, status_filter: QuestionStatus) -> list[Question]:
    stmt = select(Question).where(Question.status == status_filter).order_by(Question.created_at)
    return list(db.scalars(stmt).all())


def approve_question(db: Session, question: Question) -> Question:
    question.status = QuestionStatus.ACTIVE
    db.commit()
    db.refresh(question)
    logger.info("Pergunta id=%s aprovada (voltou para active) por moderacao", question.id)
    return question


def remove_question(db: Session, question: Question) -> Question:
    question.status = QuestionStatus.REMOVED
    db.commit()
    db.refresh(question)
    logger.info("Pergunta id=%s removida por moderacao", question.id)
    return question


def accept_report(db: Session, report: Report) -> Report:
    """Veredito individual do admin sobre ESTE reporte -- independente do
    status da pergunta (Aprovar/Remover continuam sendo acoes separadas).
    Alimenta a reputacao de quem reportou (services/stats.compute_user_reputation).
    """
    report.status = ReportStatus.ACCEPTED
    db.commit()
    db.refresh(report)
    logger.info("Reporte id=%s aceito por moderacao", report.id)
    return report


def reject_report(db: Session, report: Report) -> Report:
    report.status = ReportStatus.REJECTED
    db.commit()
    db.refresh(report)
    logger.info("Reporte id=%s rejeitado por moderacao", report.id)
    return report


async def update_question(
    db: Session,
    question: Question,
    statement: str | None,
    correct_answer: bool | None,
    category: str | None,
) -> Question:
    if statement is not None and statement != question.statement:
        question.statement = statement
        question.embedding = await get_embedding(statement)
    if correct_answer is not None:
        question.correct_answer = correct_answer
    if category is not None:
        question.category = category

    db.commit()
    db.refresh(question)
    logger.info("Pergunta id=%s editada por moderacao", question.id)
    return question
