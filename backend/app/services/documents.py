from pathlib import Path
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models import Document
from backend.app.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentStatusResponse,
)


def create_document(
    db: Session,
    document: DocumentCreate,
    user_id: int,
    file_path: str,
    idempotency_key: str | None = None,
    content_sha256: str | None = None,
) -> Document:
    db_document = Document(
        user_id=user_id,
        filename=document.filename,
        stored_filename=document.stored_filename,
        file_path=file_path,
        file_size=document.file_size,
        content_type=document.content_type,
        idempotency_key=idempotency_key,
        content_sha256=content_sha256,
        status=document.status,
    )

    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    return db_document


def get_documents(db: Session, user_id: int) -> List[Document]:
    return (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .all()
    )


def get_document(
    db: Session,
    document_id: int,
    user_id: int,
) -> Document:
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


def delete_document(
    db: Session,
    document_id: int,
    user_id: int,
) -> bool:
    document = get_document(db, document_id, user_id)

    # DELETING is persisted first because the SQL row, file and Chroma vectors
    # cannot participate in one distributed transaction. Keep the row if any
    # compensating cleanup fails so an operator can reconcile it.
    document.status = "deleting"
    db.commit()
    try:
        from backend.app.services.vector_store import delete_document_vectors
        delete_document_vectors(document.id)
        path = Path(document.file_path)
        if path.is_file():
            path.unlink()
        db.delete(document)
        db.commit()
        return True
    except Exception:
        db.rollback()
        retained = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
        if retained:
            retained.status = "failed"
            retained.processing_error = "Deletion did not complete; retry or reconcile storage"
            db.commit()
        raise


def get_document_status(
    db: Session,
    document_id: int,
    user_id: int,
) -> DocumentStatusResponse:
    document = get_document(db, document_id, user_id)

    file_exists = (
        bool(document.file_path)
        and Path(document.file_path).exists()
    )

    return DocumentStatusResponse(
        status=document.status,
        file_exists=file_exists,
    )
