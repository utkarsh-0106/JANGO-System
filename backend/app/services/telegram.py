"""Telegram Bot API helpers and private-chat command handling for JANGO."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.db import SessionLocal
from backend.app.models import Document, User
from backend.app.schemas.rag import RagRequest
from backend.app.services.rag import query_rag
from backend.app.settings import settings

logger = logging.getLogger("jango.telegram")
TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_TELEGRAM_TEXT = 4000


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def telegram_enabled() -> bool:
    return bool((settings.TELEGRAM_BOT_TOKEN or "").strip())


def telegram_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not telegram_enabled():
        raise RuntimeError("Telegram bot is not configured")
    url = f"{TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"
    with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API rejected method {method}")
    return data


def send_message(chat_id: int, text: str) -> None:
    # Telegram text messages are limited; split at line boundaries where possible.
    remaining = text.strip() or "JANGO couldn't produce a response. Please try again."
    while remaining:
        if len(remaining) <= MAX_TELEGRAM_TEXT:
            part, remaining = remaining, ""
        else:
            split_at = remaining.rfind("\n", 0, MAX_TELEGRAM_TEXT)
            if split_at < MAX_TELEGRAM_TEXT // 2:
                split_at = MAX_TELEGRAM_TEXT
            part, remaining = remaining[:split_at], remaining[split_at:].lstrip()
        telegram_api("sendMessage", {"chat_id": chat_id, "text": part, "disable_web_page_preview": True})


def send_document(chat_id: int, file_path: str, filename: str, caption: str | None = None) -> None:
    """Send a verified local file to a private Telegram chat."""
    if not telegram_enabled():
        raise RuntimeError("Telegram bot is not configured")
    path = __import__("pathlib").Path(file_path)
    if not path.is_file():
        raise FileNotFoundError("The requested document is unavailable")
    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:900]
    url = f"{TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendDocument"
    with path.open("rb") as stream:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=5.0)) as client:
            response = client.post(url, data=data, files={"document": (filename, stream, "application/octet-stream")})
            response.raise_for_status()
            result = response.json()
    if not result.get("ok"):
        raise RuntimeError("Telegram API rejected document delivery")


def send_text_file(chat_id: int, filename: str, content: str, caption: str | None = None) -> None:
    """Deliver a generated summary/report as a UTF-8 text attachment."""
    import io
    if not telegram_enabled():
        raise RuntimeError("Telegram bot is not configured")
    safe_name = __import__("pathlib").Path(filename or "jango-report.txt").name
    if not safe_name.lower().endswith(".txt"):
        safe_name += ".txt"
    url = f"{TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendDocument"
    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:900]
    with httpx.Client(timeout=httpx.Timeout(45.0, connect=5.0)) as client:
        response = client.post(
            url,
            data=data,
            files={"document": (safe_name, io.BytesIO(content.encode("utf-8")), "text/plain; charset=utf-8")},
        )
        response.raise_for_status()
        result = response.json()
    if not result.get("ok"):
        raise RuntimeError("Telegram API rejected report delivery")


def _source_footer(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "\n\nSources: no matching document passages were found."
    lines = ["\n\nSources:"]
    seen: set[tuple[str, str]] = set()
    for source in sources:
        filename = str(source.get("filename") or "Unknown document")[:180]
        page = str(source.get("page_number") or "Unknown")[:30]
        key = (filename, page)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"• {filename} — page {page}")
        if len(lines) >= 8:
            break
    return "\n".join(lines)


def _help_text() -> str:
    return (
        "Hi! I'm JANGO, your document Q&A assistant.\n\n"
        "First, link this Telegram account to your JANGO account using a link code generated in the JANGO web app.\n\n"
        "Commands:\n"
        "/link CODE — link your account\n"
        "/ask your question — ask about your documents\n"
        "/documents — list your documents\n"
        "/help — show this help\n\n"
        "You can also send a question as a normal message after linking."
    )


def _handle_link(message: dict[str, Any], db: Session, chat_id: int, args: str) -> None:
    telegram_user_id = message.get("from", {}).get("id")
    if not isinstance(telegram_user_id, int):
        send_message(chat_id, "I couldn't verify your Telegram account. Please try again in a private chat.")
        return
    code = args.strip().split()[0] if args.strip() else ""
    if not code or len(code) > 200:
        send_message(chat_id, "Use /link CODE. Generate a one-time link code from the authenticated JANGO web app first.")
        return
    now = datetime.utcnow()
    user = (
        db.query(User)
        .filter(User.telegram_link_token_hash == token_hash(code), User.telegram_link_expires_at > now)
        .first()
    )
    if not user:
        send_message(chat_id, "That link code is invalid or expired. Generate a new code in JANGO and try again.")
        return
    if user.telegram_user_id and user.telegram_user_id != telegram_user_id:
        send_message(chat_id, "This JANGO account is already linked to another Telegram account. Unlink it from JANGO first.")
        return
    already_linked = db.query(User).filter(User.telegram_user_id == telegram_user_id, User.id != user.id).first()
    if already_linked:
        send_message(chat_id, "This Telegram account is already linked to another JANGO account. Contact the JANGO administrator if this is unexpected.")
        return
    user.telegram_user_id = telegram_user_id
    user.telegram_link_token_hash = None
    user.telegram_link_expires_at = None
    db.commit()
    send_message(chat_id, f"Account linked successfully, {user.username}! You can now ask questions about your JANGO documents.")


def _handle_question(chat_id: int, user: User, db: Session, question: str) -> None:
    question = question.strip()
    if not question:
        send_message(chat_id, "Please include a question, for example: /ask Summarize my latest report")
        return
    if len(question) > 4000:
        send_message(chat_id, "That question is too long. Please keep it under 4,000 characters.")
        return
    try:
        result = query_rag(RagRequest(question=question, top_k=5, response_language="auto"), user.id, db=db)
        answer = result.answer + _source_footer(result.sources)
        send_message(chat_id, answer)
    except HTTPException as exc:
        if exc.status_code == 503:
            send_message(chat_id, "JANGO's AI provider is temporarily unavailable. Please try again shortly.")
        else:
            send_message(chat_id, "I couldn't answer that question right now. Please try again shortly.")
    except Exception:
        logger.exception("Telegram question handling failed")
        try:
            send_message(chat_id, "Something went wrong while processing your question. Please try again shortly.")
        except Exception:
            logger.warning("Unable to send Telegram failure response")


def process_update(update: dict[str, Any]) -> None:
    """Process a Telegram update in a background task; never trust chat IDs as identity."""
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    chat_id = chat.get("id")
    text = message.get("text")
    # Only private chats are supported; this avoids leaking document data in groups.
    if chat.get("type") != "private" or not isinstance(chat_id, int) or not isinstance(text, str):
        return
    text = text.strip()
    command, _, args = text.partition(" ")
    command = command.split("@", 1)[0].lower()

    if command in ("/start", "/help"):
        send_message(chat_id, _help_text())
        return

    db = SessionLocal()
    try:
        if command == "/link":
            _handle_link(message, db, chat_id, args)
            return

        telegram_user_id = sender.get("id")
        if not isinstance(telegram_user_id, int):
            send_message(chat_id, "I couldn't verify your Telegram account.")
            return
        user = db.query(User).filter(User.telegram_user_id == telegram_user_id, User.is_active.is_(True)).first()
        if not user:
            send_message(chat_id, "Your Telegram account isn't linked yet. Sign in to JANGO, generate a link code, then send /link CODE here.")
            return

        if command == "/documents":
            docs = db.query(Document).filter(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(20).all()
            if not docs:
                send_message(chat_id, "You don't have any uploaded documents yet. Upload a PDF in JANGO first.")
                return
            lines = ["Your latest JANGO documents:"]
            for doc in docs:
                lines.append(f"• {doc.filename} — {doc.status}")
            send_message(chat_id, "\n".join(lines))
            return

        if command == "/ask":
            question = args
        elif text.startswith("/"):
            send_message(chat_id, "Unknown command. Send /help to see available commands.")
            return
        else:
            question = text
        _handle_question(chat_id, user, db, question)
    finally:
        db.close()
