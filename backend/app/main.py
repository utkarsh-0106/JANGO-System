from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging
import re
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from backend.app.api.auth import router as auth_router
from backend.app.api.settings import router as settings_router
from backend.app.db import Base, engine
from backend.app.models import AIUsage, Document, User
from backend.app.routers.documents import router as documents_router
from backend.app.routers.rag import router as rag_router
from backend.app.routers.usage import router as usage_router
from backend.app.routers.telegram import router as telegram_router
from backend.app.settings import settings

logger = logging.getLogger("jango.http")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The single-machine deployment uses SQLite; create the complete schema
    # on first startup so a fresh persistent volume is immediately usable.
    Base.metadata.create_all(bind=engine)
    # create_all does not add columns to existing databases; add nullable
    # idempotency/hash columns before creating their indexes.
    inspector = inspect(engine)
    # create_all does not alter an existing users table. Add Telegram columns
    # in a backward-compatible way so existing accounts and data are preserved.
    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as connection:
            if "preferred_response_language" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN preferred_response_language VARCHAR(20) NOT NULL DEFAULT 'auto'"))
            if "retrieval_top_k" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN retrieval_top_k INTEGER NOT NULL DEFAULT 5"))
            if "telegram_user_id" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN telegram_user_id BIGINT"))
            if "telegram_link_token_hash" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN telegram_link_token_hash VARCHAR(64)"))
            if "telegram_link_expires_at" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN telegram_link_expires_at TIMESTAMP"))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_telegram_user_id "
                "ON users (telegram_user_id)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_users_telegram_link_token_hash "
                "ON users (telegram_link_token_hash)"
            ))
    if "documents" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("documents")}
        with engine.begin() as connection:
            if "idempotency_key" not in columns:
                connection.execute(text(
                    "ALTER TABLE documents ADD COLUMN idempotency_key VARCHAR(128)"
                ))
            if "content_sha256" not in columns:
                connection.execute(text(
                    "ALTER TABLE documents ADD COLUMN content_sha256 VARCHAR(64)"
                ))
            if "processing_error" not in columns:
                connection.execute(text("ALTER TABLE documents ADD COLUMN processing_error TEXT"))
            if "processing_started_at" not in columns:
                connection.execute(text("ALTER TABLE documents ADD COLUMN processing_started_at TIMESTAMP"))
            if "processed_at" not in columns:
                connection.execute(text("ALTER TABLE documents ADD COLUMN processed_at TIMESTAMP"))
            if "ingestion_attempts" not in columns:
                connection.execute(text("ALTER TABLE documents ADD COLUMN ingestion_attempts INTEGER NOT NULL DEFAULT 0"))

        # Backfill hashes for existing documents without changing/deleting records.
        # If legacy duplicates exist, keep the hash on the oldest record only; this
        # permits a unique index while preserving every existing row and its vectors.
        from pathlib import Path
        import hashlib

        with engine.begin() as connection:
            rows = connection.execute(text(
                "SELECT id, user_id, file_path, content_sha256 FROM documents "
                "ORDER BY id ASC"
            )).mappings().all()
            seen = set()
            for row in rows:
                if row["content_sha256"]:
                    key = (row["user_id"], row["content_sha256"])
                    if key in seen:
                        continue
                    seen.add(key)
                    continue
                file_path = Path(row["file_path"]) if row["file_path"] else None
                if not file_path or not file_path.is_file():
                    continue
                digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
                key = (row["user_id"], digest)
                if key in seen:
                    # Preserve the legacy duplicate row, but leave its hash NULL.
                    continue
                connection.execute(
                    text("UPDATE documents SET content_sha256 = :digest WHERE id = :id"),
                    {"digest": digest, "id": row["id"]},
                )
                seen.add(key)

        with engine.begin() as connection:
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_user_idempotency_key "
                "ON documents (user_id, idempotency_key)"
            ))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_user_content_sha256 "
                "ON documents (user_id, content_sha256)"
            ))
    # In-process FastAPI background tasks are not durable. Never leave jobs
    # showing as active forever after a process restart; mark stale work failed
    # so the owner can explicitly retry it.
    if "documents" in inspect(engine).get_table_names():
        cutoff = datetime.utcnow() - timedelta(minutes=15)
        with engine.begin() as connection:
            connection.execute(text(
                "UPDATE documents SET status='failed', processing_error='Interrupted by server restart' "
                "WHERE status='processing' AND (processing_started_at IS NULL OR processing_started_at < :cutoff)"
            ), {"cutoff": cutoff})
    yield

app = FastAPI(
    title="Enterprise Document RAG Knowledge Base",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_observability(request, call_next):
    """Attach a request ID and log latency without logging query/body data."""
    request_id = request.headers.get("x-request-id", "").strip()
    if not request_id or len(request_id) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", request_id):
        request_id = uuid.uuid4().hex

    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "http_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
        )
        return response
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "http_request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id, request.method, request.url.path, duration_ms,
        )
        raise


@app.get("/api/health")
async def health_check():
    """Liveness: the ASGI process is running."""
    return {"status": "healthy"}


@app.get("/api/ready")
async def readiness_check():
    """Readiness: verify the SQL database and configured local storage paths."""
    from pathlib import Path
    from sqlalchemy import text as sql_text
    try:
        with engine.connect() as connection:
            connection.execute(sql_text("SELECT 1"))
        Path(settings.DOCUMENT_STORAGE_DIRECTORY).mkdir(parents=True, exist_ok=True)
        Path(settings.CHROMA_PERSIST_DIRECTORY).mkdir(parents=True, exist_ok=True)
        return {"status": "ready", "database": "connected", "storage": "configured"}
    except Exception as exc:
        logger.error("readiness_check_failed error_type=%s", type(exc).__name__)
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Service dependencies are not ready") from exc


app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(documents_router)
app.include_router(rag_router, prefix="/api")
app.include_router(usage_router, prefix="/api")
app.include_router(telegram_router, prefix="/api")
