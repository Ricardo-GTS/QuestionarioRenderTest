from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.question import Question
from app.models.user import User
from app.schemas.quiz import QuizOut, QuizQuestionOut, QuizResult, QuizSubmit
from app.services.quiz import pick_random_questions, score_quiz

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.get("", response_model=QuizOut)
def get_quiz(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> QuizOut:
    questions = pick_random_questions(db, exclude_author_id=current_user.id)
    return QuizOut(
        questions=[QuizQuestionOut(id=q.id, statement=q.statement, category=q.category) for q in questions]
    )


@router.post("/submit", response_model=QuizResult)
def submit_quiz(
    payload: QuizSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizResult:
    question_ids = [answer.question_id for answer in payload.answers]
    if not question_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No answers submitted")

    questions = list(db.scalars(select(Question).where(Question.id.in_(question_ids))).all())
    answers = {answer.question_id: answer.answer for answer in payload.answers}

    result = score_quiz(questions, answers)
    return QuizResult(**result)
