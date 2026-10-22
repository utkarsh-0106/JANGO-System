"""Authenticated link-code endpoint and secret-protected Telegram webhook."""
import logging
import secrets
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.db import get_db
from backend.app.models import Document, User
from backend.app.services.telegram import process_update, send_document, send_text_file, telegram_enabled, token_hash
from backend.app.settings import settings

logger = logging.getLogger("jango.telegram")
router = APIRouter(prefix="/telegram", tags=["telegram"])


class TelegramDeliveryRequest(BaseModel):
    kind: Literal["document", "summary", "report"]
    document_id: int | None = Field(default=None, ge=1)
    title: str = Field(default="JANGO report", min_length=1, max_length=180)
    content: str | None = Field(default=None, max_length=100_000)


@router.get("/status")
def telegram_status(current_user: User = Depends(get_current_user)):
    return {
        "configured": telegram_enabled(),
        "linked": bool(current_user.telegram_user_id),
        "bot_username": None,
    }


@router.post("/send")
def send_to_telegram(
    payload: TelegramDeliveryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deliver a user's own source PDF or generated text report to their linked private chat."""
    if not telegram_enabled():
        raise HTTPException(status_code=503, detail="Telegram integration is not configured")
    if not current_user.telegram_user_id:
        raise HTTPException(status_code=409, detail="Connect your Telegram account first.")
    chat_id = int(current_user.telegram_user_id)

    if payload.kind == "document":
        if payload.document_id is None:
            raise HTTPException(status_code=422, detail="document_id is required")
        document = (
            db.query(Document)
            .filter(Document.id == payload.document_id, Document.user_id == current_user.id)
            .first()
        )
        if not document:
            # Avoid disclosing whether another user's document exists.
            raise HTTPException(status_code=404, detail="Document not found")
        path = Path(document.file_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="The stored document file is unavailable")
        if path.stat().st_size > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Telegram document delivery is limited to 50 MB")
        try:
            send_document(chat_id, str(path), Path(document.filename).name, "Sent from your JANGO workspace")
        except Exception as exc:
            logger.warning("Telegram document delivery failed for user_id=%s document_id=%s: %s", current_user.id, document.id, type(exc).__name__)
            raise HTTPException(status_code=502, detail="Telegram could not deliver this document. Please try again.") from exc
        return {"ok": True, "kind": "document", "filename": document.filename}

    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="Report content is required")
    if payload.kind == "summary":
        content = f"{payload.title}\n\n{content}"
    try:
        safe_title = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in payload.title).strip(" .")[:100] or "JANGO report"
        send_text_file(chat_id, f"{safe_title}.txt", content, "JANGO " + payload.kind)
    except Exception as exc:
        logger.warning("Telegram report delivery failed for user_id=%s kind=%s: %s", current_user.id, payload.kind, type(exc).__name__)
        raise HTTPException(status_code=502, detail="Telegram could not deliver this report. Please try again.") from exc
    return {"ok": True, "kind": payload.kind, "filename": f"{safe_title}.txt"}


@router.post("/link-code")
def create_telegram_link_code(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not telegram_enabled():
        raise HTTPException(status_code=503, detail="Telegram integration is not configured")
    code = secrets.token_urlsafe(24)
    current_user.telegram_link_token_hash = token_hash(code)
    current_user.telegram_link_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.add(current_user)
    db.commit()
    return {
        "code": code,
        "expires_in_seconds": 600,
        "instruction": "Open your JANGO Telegram bot in a private chat and send /link followed by this code. The code can only be used once.",
    }


@router.post("/webhook", status_code=status.HTTP_200_OK)
def telegram_webhook(
    update: dict,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not telegram_enabled():
        raise HTTPException(status_code=503, detail="Telegram integration is not configured")
    expected = (settings.TELEGRAM_WEBHOOK_SECRET or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Telegram webhook secret is not configured")
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(x_telegram_bot_api_secret_token, expected):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    if not isinstance(update, dict) or not isinstance(update.get("update_id"), int):
        raise HTTPException(status_code=400, detail="Invalid Telegram update")
    # Return quickly so Telegram does not retry while LLM inference is running.
    background_tasks.add_task(process_update, update)
    return {"ok": True}
