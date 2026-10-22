from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.auth import get_current_user
from backend.app.db import get_db
from backend.app.routers import telegram as telegram_router


class FakeQuery:
    def __init__(self, result):
        self.result = result
    def filter(self, *args, **kwargs):
        return self
    def first(self):
        return self.result


class FakeDB:
    def __init__(self, document=None):
        self.document = document
    def query(self, model):
        return FakeQuery(self.document)


def test_send_requires_linked_telegram_account(monkeypatch):
    monkeypatch.setattr(telegram_router, "telegram_enabled", lambda: True)
    user = SimpleNamespace(id=7, telegram_user_id=None)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: FakeDB()
    try:
        response = TestClient(app).post("/api/telegram/send", json={"kind": "summary", "title": "Summary", "content": "Hello"})
        assert response.status_code == 409
        assert "Connect your Telegram account" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_send_document_does_not_disclose_other_users_document(monkeypatch, tmp_path):
    monkeypatch.setattr(telegram_router, "telegram_enabled", lambda: True)
    user = SimpleNamespace(id=7, telegram_user_id=1234)
    # The query result is None when the document does not belong to the current user.
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: FakeDB(document=None)
    try:
        response = TestClient(app).post("/api/telegram/send", json={"kind": "document", "document_id": 99})
        assert response.status_code == 404
        assert response.json()["detail"] == "Document not found"
    finally:
        app.dependency_overrides.clear()


def test_report_requires_content(monkeypatch):
    monkeypatch.setattr(telegram_router, "telegram_enabled", lambda: True)
    user = SimpleNamespace(id=7, telegram_user_id=1234)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: FakeDB()
    try:
        response = TestClient(app).post("/api/telegram/send", json={"kind": "report", "title": "Report", "content": " "})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
