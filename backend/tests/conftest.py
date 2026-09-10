import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://questionario:questionario@localhost:5432/questionario_test",
    ),
)

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models  # noqa: E402,F401  (registra os modelos em Base.metadata)
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402


def _database_available() -> bool:
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _database_available(),
    reason="Banco de dados de teste (Postgres + pgvector) indisponivel",
)


@pytest.fixture()
def db_session():
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    import app.api.routers.questions as questions_router
    from app.api.deps import get_db
    from app.main import app

    async def fake_get_embedding(text: str) -> list[float]:
        """Embedding deterministico (mesmo texto -> mesmo vetor) so para testes, sem chamar o Ollama."""
        seed = float(sum(ord(c) for c in text) % 1000)
        return [seed] + [0.0] * 767

    monkeypatch.setattr(questions_router, "get_embedding", fake_get_embedding)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
