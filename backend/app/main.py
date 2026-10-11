from contextlib import asynccontextmanager
import logging
import re
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
