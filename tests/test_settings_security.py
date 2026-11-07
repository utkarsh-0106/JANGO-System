import pytest
from pydantic import ValidationError

from backend.app.settings import Settings


def test_production_rejects_sqlite_database():
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///./jango.db",
            SECRET_KEY="s" * 40,
            CORS_ORIGINS="https://example.com",
        )


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError, match="32 characters"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost/jango",
            SECRET_KEY="short",
            CORS_ORIGINS="https://example.com",
        )


def test_production_accepts_explicit_postgres_and_origin():
    configured = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql://user:pass@localhost/jango",
        SECRET_KEY="s" * 40,
        CORS_ORIGINS="https://example.com",
    )
    assert configured.cors_origin_list == ["https://example.com"]
