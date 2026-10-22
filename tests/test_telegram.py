from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import telegram as telegram_router
from backend.app.services import telegram as telegram_service


def test_webhook_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(telegram_router, "telegram_enabled", lambda: True)
    monkeypatch.setattr(telegram_router.settings, "TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    client = TestClient(app)
    response = client.post(
        "/api/telegram/webhook",
        json={"update_id": 1, "message": {}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert response.status_code == 403


def test_webhook_rejects_missing_secret(monkeypatch):
    monkeypatch.setattr(telegram_router, "telegram_enabled", lambda: True)
    monkeypatch.setattr(telegram_router.settings, "TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    client = TestClient(app)
    response = client.post("/api/telegram/webhook", json={"update_id": 1, "message": {}})
    assert response.status_code == 403


def test_webhook_queues_update(monkeypatch):
    monkeypatch.setattr(telegram_router, "telegram_enabled", lambda: True)
    monkeypatch.setattr(telegram_router.settings, "TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    client = TestClient(app)
    response = client.post(
        "/api/telegram/webhook",
        json={"update_id": 1, "message": {"text": "hello"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_token_hash_is_deterministic_and_not_plaintext():
    hashed = telegram_service.token_hash("one-time-code")
    assert hashed == telegram_service.token_hash("one-time-code")
    assert hashed != "one-time-code"
    assert len(hashed) == 64


def test_private_chat_only(monkeypatch):
    sent = []
    monkeypatch.setattr(telegram_service, "send_message", lambda chat_id, text: sent.append((chat_id, text)))
    telegram_service.process_update({"update_id": 1, "message": {"chat": {"id": -100, "type": "group"}, "from": {"id": 1}, "text": "secret question"}})
    assert sent == []
