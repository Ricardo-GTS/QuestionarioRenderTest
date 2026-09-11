from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.app_settings import AppSettings

SETTINGS_ROW_ID = 1


def get_effective_settings(db: Session) -> AppSettings:
    """Le os parametros de negocio efetivos (tabela app_settings).

    A migration 0002 ja semeia a linha id=1; o fallback aqui e só defensivo
    (ex: banco criado fora do fluxo normal de migrations).
    """
    row = db.get(AppSettings, SETTINGS_ROW_ID)
    if row is None:
        row = AppSettings(
            id=SETTINGS_ROW_ID,
            similarity_threshold=settings.similarity_threshold,
            quiz_size=settings.quiz_size,
            report_threshold=settings.report_threshold,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def update_settings(
    db: Session,
    similarity_threshold: float | None = None,
    quiz_size: int | None = None,
    report_threshold: int | None = None,
) -> AppSettings:
    if similarity_threshold is not None and not (0 < similarity_threshold <= 1):
        raise ValueError("similarity_threshold deve estar entre 0 (exclusivo) e 1 (inclusivo)")
    if quiz_size is not None and quiz_size <= 0:
        raise ValueError("quiz_size deve ser maior que zero")
    if report_threshold is not None and report_threshold <= 0:
        raise ValueError("report_threshold deve ser maior que zero")

    row = get_effective_settings(db)
    if similarity_threshold is not None:
        row.similarity_threshold = similarity_threshold
    if quiz_size is not None:
        row.quiz_size = quiz_size
    if report_threshold is not None:
        row.report_threshold = report_threshold

    db.commit()
    db.refresh(row)
    return row
