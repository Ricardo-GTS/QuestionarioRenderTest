import logging

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    checks = {"database": False, "ollama": False}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        logger.exception("Healthcheck: falha ao conectar ao Postgres")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(settings.ollama_host)
            response.raise_for_status()
        checks["ollama"] = True
    except Exception:
        logger.exception("Healthcheck: falha ao conectar ao Ollama")

    status_ok = all(checks.values())
    return {"status": "ok" if status_ok else "degraded", "checks": checks}
