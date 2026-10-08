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
) -> Document:
    db_document = Document(
        user_id=user_id,
        filename=document.filename,
        stored_filename=document.stored_filename,
        file_path=file_path,
        file_size=document.file_size,
        content_type=document.content_type,
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

    # Remove the document's vectors from ChromaDB first.
    try:
        from backend.app.services.vector_store import delete_document_vectors
        delete_document_vectors(document.id)
    except Exception:
        # Do not delete the database record if vector cleanup fails.
        raise

    db.delete(document)
    db.commit()

    return True


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
