from pathlib import Path

from fastapi import HTTPException, status
from langchain_core.documents import Document as LangChainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy.orm import Session
from backend.app.db import SessionLocal

from backend.app.models import Document
from backend.app.services.documents import get_document
from backend.app.services.vector_store import (
    add_chunks,
    delete_document_vectors,
)


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def ingest_document(
    document_id: int,
    db: Session,
    user_id: int,
) -> bool:
    document = get_document(
        db,
        document_id,
        user_id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = Path(document.file_path)

    if not file_path.exists():
        document.status = "failed"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )

    if not document.content_type == "application/pdf":
        document.status = "failed"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents can be ingested",
        )

    try:
        document.status = "processing"
        db.commit()

        # Remove old vectors so reprocessing does not create duplicates.
        delete_document_vectors(document.id)

        reader = PdfReader(str(file_path))

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        chunks: list[LangChainDocument] = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""

            text = text.strip()

            if not text:
                continue

            page_chunks = splitter.split_text(text)

            for chunk in page_chunks:
                chunks.append(
                    LangChainDocument(
                        page_content=chunk,
                        metadata={
                            "document_id": int(document.id),
                            "user_id": int(document.user_id),
                            "filename": document.filename,
                            "page_number": int(page_number),
                        },
                    )
                )

        if not chunks:
            raise ValueError(
                "No extractable text was found in the PDF"
            )

        add_chunks(chunks)

        document.status = "ready"
        db.commit()
        db.refresh(document)

        return True

    except HTTPException:
        document.status = "failed"
        db.commit()
        raise

    except Exception as exc:
        document.status = "failed"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document ingestion failed: {exc}",
        ) from exc


def reprocess_document(
    document_id: int,
    db: Session,
    user_id: int,
) -> bool:
    return ingest_document(
        document_id=document_id,
        db=db,
        user_id=user_id,
    )
def ingest_document_background(
    document_id: int,
    user_id: int,
) -> None:
    db = SessionLocal()

    try:
        ingest_document(
            document_id=document_id,
            db=db,
            user_id=user_id,
        )
    finally:
        db.close()
