from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routers import admin, auth, health, questions, quiz, reports
from app.core.logging import configure_logging
from app.core.rate_limit import limiter

configure_logging()

app = FastAPI(title="Questionario API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(quiz.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.get("/")
def root() -> dict:
    return {"status": "ok"}
