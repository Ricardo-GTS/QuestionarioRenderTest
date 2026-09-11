from fastapi import FastAPI

from app.api.routers import admin, auth, health, questions, quiz, reports
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="Questionario API")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(quiz.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.get("/")
def root() -> dict:
    return {"status": "ok"}
