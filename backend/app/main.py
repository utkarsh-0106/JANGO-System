from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.auth import router as auth_router
from backend.app.db import Base, engine
from backend.app.models import AIUsage, Document, User
from backend.app.routers.documents import router as documents_router
from backend.app.routers.rag import router as rag_router
from backend.app.routers.usage import router as usage_router
from backend.app.settings import settings


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


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(rag_router, prefix="/api")
app.include_router(usage_router, prefix="/api")
