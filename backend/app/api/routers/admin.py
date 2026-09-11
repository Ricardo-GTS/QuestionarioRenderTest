import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.core.security import is_admin_email
from app.models.enums import QuestionStatus
from app.models.question import Question
from app.models.user import User
from app.schemas.admin import (
    AdminQuestionOut,
    AdminQuestionUpdate,
    AdminStatsOut,
    AdminUserOut,
    AppSettingsOut,
    AppSettingsUpdate,
)
from app.services import moderation as moderation_service
from app.services.embeddings import EmbeddingServiceError
from app.services.runtime_settings import get_effective_settings, update_settings
from app.services.stats import compute_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _with_report_info(question: Question) -> Question:
    question.report_count = len(question.reports)
    question.report_reasons = [report.reason for report in question.reports]
    return question


@router.get("/settings", response_model=AppSettingsOut)
def read_settings(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AppSettingsOut:
    return get_effective_settings(db)


@router.put("/settings", response_model=AppSettingsOut)
def write_settings(
    payload: AppSettingsUpdate,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AppSettingsOut:
    try:
        return update_settings(
            db,
            similarity_threshold=payload.similarity_threshold,
            quiz_size=payload.quiz_size,
            report_threshold=payload.report_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/questions", response_model=list[AdminQuestionOut])
def list_questions(
    question_status: QuestionStatus = Query(default=QuestionStatus.REPORTED, alias="status"),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[Question]:
    questions = moderation_service.list_questions_by_status(db, question_status)
    return [_with_report_info(q) for q in questions]


def _get_question_or_404(db: Session, question_id: int) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


@router.put("/questions/{question_id}/approve", response_model=AdminQuestionOut)
def approve_question(
    question_id: int,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Question:
    question = _get_question_or_404(db, question_id)
    question = moderation_service.approve_question(db, question)
    return _with_report_info(question)


@router.put("/questions/{question_id}/remove", response_model=AdminQuestionOut)
def remove_question(
    question_id: int,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Question:
    question = _get_question_or_404(db, question_id)
    question = moderation_service.remove_question(db, question)
    return _with_report_info(question)


@router.put("/questions/{question_id}", response_model=AdminQuestionOut)
async def update_question(
    question_id: int,
    payload: AdminQuestionUpdate,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Question:
    question = _get_question_or_404(db, question_id)
    try:
        question = await moderation_service.update_question(
            db,
            question,
            statement=payload.statement,
            correct_answer=payload.correct_answer,
            category=payload.category,
        )
    except EmbeddingServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _with_report_info(question)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    users = list(db.scalars(select(User).order_by(User.created_at)).all())
    for user in users:
        user.is_admin = is_admin_email(user.email)
        user.question_count = len(user.questions)
    return users


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use DELETE /auth/me para excluir a propria conta",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()
    logger.info("Usuario id=%s removido pelo admin id=%s", user_id, admin.id)


@router.get("/stats", response_model=AdminStatsOut)
def read_stats(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminStatsOut:
    return AdminStatsOut(**compute_stats(db))
