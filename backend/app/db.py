"""SQLAlchemy engine and request-scoped session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.settings import settings

_url = settings.DATABASE_URL.strip()
# Render commonly supplies postgres:// while SQLAlchemy 2 + psycopg v3 uses
# the explicit postgresql+psycopg dialect. Never fall back to SQLite.
if _url.startswith("postgres://"):
    _url = "postgresql+psycopg://" + _url[len("postgres://"):]
elif _url.startswith("postgresql://") and "+" not in _url.split(":", 1)[0]:
    _url = "postgresql+psycopg://" + _url[len("postgresql://"):]
_engine_options = {"pool_pre_ping": True}
if _url.startswith("sqlite"):
    _engine_options.update(connect_args={"check_same_thread": False, "timeout": 30})
else:
    # QueuePool defaults are suitable for a single API process; keep the pool
    # bounded so multiple Render workers do not exhaust PostgreSQL connections.
    _engine_options.update(pool_size=settings.DB_POOL_SIZE, max_overflow=settings.DB_MAX_OVERFLOW, pool_timeout=30, pool_recycle=1800)

engine = create_engine(_url, **_engine_options)

if _url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
