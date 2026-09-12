from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSettings(Base):
    """Linha unica (id=1) com os parametros de negocio editaveis via /admin/settings."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    similarity_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    quiz_size: Mapped[int] = mapped_column(Integer, nullable=False)
    report_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
