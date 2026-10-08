from backend.app.settings import settings


class AIProviderConfigError(ValueError):
    """Raised when the selected AI provider is missing required configuration."""


def normalize_provider(value: str) -> str:
    value = (value or "").strip().lower()
    aliases = {
        "google": "gemini",
        "google-genai": "gemini",
        "anthropic": "claude",
        "claude": "claude",
    }
    return aliases.get(value, value)


def _require(value: str | None, name: str) -> str:
    value = (value or "").strip()
    if not value:
        raise AIProviderConfigError(f"{name} must be set for the selected AI provider")
    return value


def require_gemini_api_key() -> str:
    return _require(settings.GEMINI_API_KEY, "GEMINI_API_KEY")


def require_groq_api_key() -> str:
    return _require(settings.GROQ_API_KEY, "GROQ_API_KEY")


def require_anthropic_api_key() -> str:
    return _require(settings.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY")
