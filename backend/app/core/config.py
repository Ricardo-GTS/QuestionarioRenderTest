from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    ollama_host: str = "http://ollama:11434"
    ollama_embed_model: str = "nomic-embed-text"

    # Defaults iniciais -- depois do primeiro boot, os valores efetivos ficam
    # em app_settings (tabela) e sao editaveis via /admin/settings. Ver
    # services/runtime_settings.py.
    similarity_threshold: float = 0.75
    quiz_size: int = 10
    report_threshold: int = 3

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 dias

    # Pool de conexoes do Postgres. Defaults do SQLAlchemy (5 + 10 overflow = 15)
    # sao baixos para varios alunos usando ao mesmo tempo; ver db/session.py.
    db_pool_size: int = 20
    db_max_overflow: int = 20

    admin_emails_raw: str = Field(default="", alias="ADMIN_EMAILS")

    @property
    def admin_emails(self) -> set[str]:
        return {email.strip().lower() for email in self.admin_emails_raw.split(",") if email.strip()}


settings = Settings()
