import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.question import Question
from app.models.user import User
from app.schemas.question import QuestionCreate, QuestionOut, SimilarQuestionOut
from app.services.embeddings import EmbeddingServiceError, get_embedding
from app.services.similarity import find_similar_active_questions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    payload: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Question:
    try:
        embedding = await get_embedding(payload.statement)
    except EmbeddingServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    similar = find_similar_active_questions(db, embedding)
    if similar:
        logger.info(
            "Pergunta descartada por similaridade (autor_id=%s, %d correspondencia(s))",
            current_user.id,
            len(similar),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Ja existe uma pergunta muito parecida com essa.",
                "similar_questions": [
                    SimilarQuestionOut(
                        id=match.question.id,
                        statement=match.question.statement,
                        category=match.question.category,
                        similarity=round(match.similarity, 4),
                    ).model_dump()
                    for match in similar
                ],
            },
        )

    question = Question(
        author_id=current_user.id,
        statement=payload.statement,
        correct_answer=payload.correct_answer,
        category=payload.category,
        embedding=embedding,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question
