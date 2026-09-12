from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Nullable porque uma conta criada via login com Google pode nao ter senha.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "sub" do id_token do Google -- identificador estavel da conta Google, distinto
    # do email (que em tese pode mudar). Null para quem nunca usou login com Google.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    questions: Mapped[list["Question"]] = relationship(back_populates="author", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="reporter", cascade="all, delete-orphan")
