from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    ollama_host: str = "http://ollama:11434"
    ollama_embed_model: str = "nomic-embed-text"

    similarity_threshold: float = 0.75
    quiz_size: int = 10
    report_threshold: int = 3

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60


settings = Settings()
