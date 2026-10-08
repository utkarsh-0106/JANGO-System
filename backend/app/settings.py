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

    # Cloud-safe defaults. Local development can explicitly set both to
    # "ollama" in .env when Ollama is running on the Mac.
    LLM_PROVIDER: str = "gemini"
    EMBEDDING_PROVIDER: str = "gemini"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_CHAT_MODEL: str = "qwen3:8b"

    GEMINI_API_KEY: str | None = None
    GEMINI_CHAT_MODEL: str = "gemini-3.8-flash"
    GEMINI_FALLBACK_MODELS: str = "gemini-3.7-flash,gemini-3.6-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"

    GROQ_API_KEY: str | None = None
    GROQ_CHAT_MODEL: str = "openai/gpt-oss-120b"

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_CHAT_MODEL: str = "claude-sonnet-4-5"

    # Comma-separated providers used only when the primary provider is
    # temporarily unavailable. Providers without an API key are skipped.
    LLM_FALLBACK_PROVIDERS: str = "groq,claude"
    AI_MAX_ATTEMPTS: int = 2
    AI_RETRY_BASE_SECONDS: float = 1.0

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
    def validate_runtime_configuration(self):
        production = self.ENVIRONMENT.lower() == "production"

        if self.SECRET_KEY in (None, "", "your-secret-key-here"):
            if production:
                raise ValueError(
                    "SECRET_KEY must be set to a non-placeholder value in production"
                )
            self.SECRET_KEY = secrets.token_urlsafe(32)

        # Render cannot reach the developer's Mac-local Ollama service.
        # If an old Render environment variable still says "ollama", use the
        # cloud Gemini path instead of allowing document ingestion/RAG to fail.
        if production and normalize_runtime_provider(self.LLM_PROVIDER) == "ollama":
            self.LLM_PROVIDER = "gemini"

        if production and normalize_runtime_provider(self.EMBEDDING_PROVIDER) == "ollama":
            self.EMBEDDING_PROVIDER = "gemini"

        return self


def normalize_runtime_provider(value: str) -> str:
    value = (value or "").strip().lower()
    return {
        "google": "gemini",
        "google-genai": "gemini",
    }.get(value, value)


settings = Settings()
