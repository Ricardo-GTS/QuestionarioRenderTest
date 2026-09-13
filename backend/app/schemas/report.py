from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import ReportStatus

# Lista fechada de tipos de problema (RF04) -- exibida como dropdown no frontend
# em vez de texto livre. Mudar aqui exige atualizar report_state.py no frontend.
REASON_CATEGORIES: tuple[str, ...] = (
    "Resposta incorreta",
    "Enunciado ambiguo ou confuso",
    "Conteudo ofensivo ou inadequado",
    "Pergunta duplicada",
    "Fora do tema",
    "Outro",
)


class ReportCreate(BaseModel):
    reason: str = Field(min_length=3)
    reason_category: Literal[REASON_CATEGORIES] | None = Field(default=None)  # type: ignore[valid-type]


class ReportOut(BaseModel):
    id: int
    question_id: int
    reporter_id: int
    reason: str
    reason_category: str | None
    status: ReportStatus
    created_at: datetime

    class Config:
        from_attributes = True
