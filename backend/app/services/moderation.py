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
    reason: str | None,
    reason_category: str,
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


def list_questions_with_pending_reports(db: Session) -> list[Question]:
    """Fila de moderacao: perguntas com pelo menos 1 reporte ainda pendente,
    independente do status da pergunta (active/reported/removed) -- assim um
    reporte nunca fica "preso" inacessivel so' porque a pergunta ja saiu do
    status "reported" (ex: foi removida antes do reporte ser resolvido)."""
    stmt = (
        select(Question)
        .join(Report, Report.question_id == Question.id)
        .where(Report.status == ReportStatus.PENDING)
        .distinct()
        .order_by(Question.created_at)
    )
    return list(db.scalars(stmt).all())


def approve_question(db: Session, question: Question) -> Question:
    """Usado pra reativar uma pergunta ja removida (aba "Perguntas Removidas").
    Nao mexe em reportes -- por essa via, os reportes dela ja foram resolvidos
    antes (ver resolve_reported_question)."""
    question.status = QuestionStatus.ACTIVE
    db.commit()
    db.refresh(question)
    logger.info("Pergunta id=%s aprovada (voltou para active) por moderacao", question.id)
    return question


def resolve_reported_question(db: Session, question: Question, approve_removal: bool) -> Question:
    """Decisao unica do admin sobre uma pergunta na fila de moderacao:
    "Aprovar Remocao" (remove a pergunta + aceita os reportes pendentes dela,
    validando quem reportou) ou "Rejeitar Remocao" (mantem/reativa a pergunta
    + rejeita os reportes pendentes, sem validar quem reportou). Resolve TODOS
    os reportes pendentes da pergunta de uma vez, nao um por um.
    """
    question.status = QuestionStatus.REMOVED if approve_removal else QuestionStatus.ACTIVE
    new_report_status = ReportStatus.ACCEPTED if approve_removal else ReportStatus.REJECTED
    for report in question.reports:
        if report.status == ReportStatus.PENDING:
            report.status = new_report_status

    db.commit()
    db.refresh(question)
    logger.info(
        "Pergunta id=%s: remocao %s, reportes pendentes marcados como %s",
        question.id,
        "aprovada" if approve_removal else "rejeitada",
        new_report_status.value,
    )
    return question


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
