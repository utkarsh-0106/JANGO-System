import secrets

from pydantic import ConfigDict, computed_field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./sql_app.db"
    SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    FRONTEND_ORIGIN: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173"

    LLM_PROVIDER: str = "ollama"
    EMBEDDING_PROVIDER: str = "ollama"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_CHAT_MODEL: str = "qwen3:8b"

    GEMINI_API_KEY: str | None = None
    GEMINI_CHAT_MODEL: str = "gemini-3.8-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"

    GROQ_API_KEY: str | None = None
    GROQ_CHAT_MODEL: str = "openai/gpt-oss-120b"

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_CHAT_MODEL: str = "claude-sonnet-4-5"

    AI_INPUT_COST_PER_1M_USD: float = 0.0
    AI_OUTPUT_COST_PER_1M_USD: float = 0.0

    CHROMA_PERSIST_DIRECTORY: str = "./storage/chroma"
    DOCUMENT_STORAGE_DIRECTORY: str = "./storage/documents"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field
    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            raw = "http://localhost:5173"
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_secret_key(self):
        if self.SECRET_KEY in (None, "", "your-secret-key-here"):
            if self.ENVIRONMENT.lower() == "production":
                raise ValueError("SECRET_KEY must be set to a non-placeholder value in production")
            self.SECRET_KEY = secrets.token_urlsafe(32)
        return self


settings = Settings()
