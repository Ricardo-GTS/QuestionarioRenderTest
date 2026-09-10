from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import QuestionStatus


class QuestionCreate(BaseModel):
    statement: str = Field(min_length=3)
    correct_answer: bool
    category: str | None = Field(default=None, max_length=120)


class QuestionOut(BaseModel):
    id: int
    author_id: int
    statement: str
    correct_answer: bool
    category: str | None
    status: QuestionStatus
    created_at: datetime

    class Config:
        from_attributes = True


class SimilarQuestionOut(BaseModel):
    id: int
    statement: str
    category: str | None
    similarity: float
