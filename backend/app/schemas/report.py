from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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
    # Tipo de problema e' obrigatorio; o texto livre e' opcional, exceto quando
    # reason_category == "Outro" (aí o texto livre e' a unica pista do motivo).
    reason: str | None = Field(default=None, min_length=3)
    reason_category: Literal[REASON_CATEGORIES]  # type: ignore[valid-type]

    @model_validator(mode="after")
    def _reason_required_for_outro(self) -> "ReportCreate":
        if self.reason_category == "Outro" and not (self.reason and self.reason.strip()):
            raise ValueError('Descreva o motivo quando o tipo de problema for "Outro"')
        return self


class ReportOut(BaseModel):
    id: int
    question_id: int
    reporter_id: int
    reason: str | None
    reason_category: str
    status: ReportStatus
    created_at: datetime

    class Config:
        from_attributes = True
