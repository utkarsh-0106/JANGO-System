from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from backend.app.main import app
from backend.app.settings import Settings


client = TestClient(app)


def test_health_does_not_require_ollama_or_gemini():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_cors_accepts_localhost():
    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "http://localhost:5173"
    )


def test_cors_unknown_origin_has_no_allow_origin():
    response = client.get(
        "/api/health",
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_accepts_configured_production_origin():
    origins = Settings(
        CORS_ORIGINS="http://localhost:5173,https://example.vercel.app",
        SECRET_KEY="test-secret",
        ENVIRONMENT="development",
    ).cors_origin_list

    isolated = FastAPI()
    isolated.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @isolated.get("/api/health")
    async def health():
        return {"status": "healthy"}

    isolated_client = TestClient(isolated)

    allowed = isolated_client.get(
        "/api/health",
        headers={"Origin": "https://example.vercel.app"},
    )
    denied = isolated_client.get(
        "/api/health",
        headers={"Origin": "https://evil.example"},
    )

    assert allowed.status_code == 200
    assert (
        allowed.headers.get("access-control-allow-origin")
        == "https://example.vercel.app"
    )
    assert denied.status_code == 200
    assert "access-control-allow-origin" not in denied.headers
