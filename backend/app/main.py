from contextlib import asynccontextmanager
import logging
import re
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from backend.app.api.auth import router as auth_router
from backend.app.db import Base, engine
from backend.app.models import AIUsage, Document, User
from backend.app.routers.documents import router as documents_router
from backend.app.routers.rag import router as rag_router
from backend.app.routers.usage import router as usage_router
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
    yield

app = FastAPI(
    title="Enterprise Document RAG Knowledge Base",
    version="1.0.0",
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
    return {"status": "healthy"}


app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(rag_router, prefix="/api")
app.include_router(usage_router, prefix="/api")
