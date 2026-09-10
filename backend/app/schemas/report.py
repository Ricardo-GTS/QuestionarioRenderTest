from datetime import datetime

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    reason: str = Field(min_length=3)
    reason_category: str | None = Field(default=None, max_length=60)


class ReportOut(BaseModel):
    id: int
    question_id: int
    reporter_id: int
    reason: str
    reason_category: str | None
    created_at: datetime

    class Config:
        from_attributes = True
