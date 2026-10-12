from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Index

from backend.app.db import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_path = Column(String(500), nullable=False)

    file_size = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=False)

    # Reused by retries of the same upload operation. Nullable for legacy records.
    idempotency_key = Column(String(128), nullable=True)

    # SHA-256 of the exact uploaded bytes; unique per user to prevent duplicate PDFs.
    content_sha256 = Column(String(64), nullable=True)

    status = Column(
        String(50),
        nullable=False,
        default="uploaded",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


Index(
    "uq_documents_user_idempotency_key",
    Document.user_id,
    Document.idempotency_key,
    unique=True,
)

Index(
    "uq_documents_user_content_sha256",
    Document.user_id,
    Document.content_sha256,
    unique=True,
)
