from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import QuestionStatus


class AppSettingsOut(BaseModel):
    similarity_threshold: float
    quiz_size: int
    report_threshold: int

    class Config:
        from_attributes = True


class AppSettingsUpdate(BaseModel):
    similarity_threshold: float | None = Field(default=None, gt=0, le=1)
    quiz_size: int | None = Field(default=None, gt=0)
    report_threshold: int | None = Field(default=None, gt=0)


class AdminQuestionOut(BaseModel):
    id: int
    author_id: int
    statement: str
    correct_answer: bool
    category: str | None
    status: QuestionStatus
    created_at: datetime
    report_count: int = 0
    report_reasons: list[str] = []

    class Config:
        from_attributes = True


class AdminQuestionUpdate(BaseModel):
    statement: str | None = Field(default=None, min_length=3)
    correct_answer: bool | None = None
    category: str | None = None


class AdminUserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime
    is_admin: bool = False
    question_count: int = 0

    class Config:
        from_attributes = True


class CategoryCount(BaseModel):
    category: str
    count: int


class AdminStatsOut(BaseModel):
    total_users: int
    total_questions_active: int
    total_questions_reported: int
    total_questions_removed: int
    total_reports: int
    total_quiz_attempts: int
    average_score_percent: float | None
    questions_by_category: list[CategoryCount]
    reports_by_category: list[CategoryCount]
