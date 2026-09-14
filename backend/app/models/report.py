from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ReportStatus


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # RF04 ajuste: um usuario so pode reportar a mesma pergunta uma vez.
        UniqueConstraint("question_id", "reporter_id", name="uq_reports_question_reporter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Opcional -- so obrigatorio quando reason_category == "Outro" (ver ReportCreate).
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_category: Mapped[str] = mapped_column(String(60), nullable=False)
    # Veredito do admin sobre ESTE reporte especifico (independente do status da
    # pergunta) -- alimenta a reputacao de quem reportou (ver services/stats.py).
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status", values_callable=lambda cls: [e.value for e in cls]),
        default=ReportStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped["Question"] = relationship(back_populates="reports")
    reporter: Mapped["User"] = relationship(back_populates="reports")
