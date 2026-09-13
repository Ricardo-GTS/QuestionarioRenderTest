from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.question import Question
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportCreate, ReportOut
from app.services.moderation import register_report

router = APIRouter(prefix="/questions", tags=["reports"])


@router.post("/{question_id}/report", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def report_question(
    question_id: int,
    payload: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    existing = db.scalar(
        select(Report).where(Report.question_id == question_id, Report.reporter_id == current_user.id)
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Voce ja reportou esta pergunta")

    return register_report(
        db,
        question=question,
        reporter_id=current_user.id,
        reason=payload.reason,
        reason_category=payload.reason_category,
    )
