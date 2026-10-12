from pathlib import Path
import re
import uuid
import hashlib
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
    Header,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi.responses import FileResponse

from ..api.auth import get_current_user
from ..db import get_db, SessionLocal
from ..models import Document
from ..schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentStatusResponse,
)
from ..services.documents import (
    create_document,
    get_documents,
    get_document,
    delete_document,
    get_document_status,
)
from ..services.ingestion import ingest_document
from ..settings import settings


router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)

STORAGE_DIR = Path(settings.DOCUMENT_STORAGE_DIRECTORY)
MAX_FILE_SIZE = 10 * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    filename = Path(filename or "document.pdf").name
    filename = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)

    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    return filename


def ingest_document_background(
    document_id: int,
    user_id: int,
):
    """
    Background task wrapper.

    Creates a fresh database session because the original
    request database session must not be reused by the
    background task.
    """
    db = SessionLocal()

    try:
        ingest_document(
            document_id=document_id,
            db=db,
            user_id=user_id,
        )
    except Exception as exc:
        print(
            f"Background ingestion failed for document "
            f"{document_id}: {exc}"
        )
    finally:
        db.close()


@router.post(
    "/upload",
    response_model=DocumentResponse,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency-Key must contain 1–128 characters",
            )
        existing = (
            db.query(Document)
            .filter(
                Document.user_id == current_user.id,
                Document.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            return existing

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded",
        )

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds maximum limit of 10 MB",
        )

    # Hash the exact bytes. Identical content gets the same hash regardless of filename.
    content_sha256 = hashlib.sha256(content).hexdigest()

    # Content deduplication is scoped to the authenticated user.
    existing_content = (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id,
            Document.content_sha256 == content_sha256,
        )
        .first()
    )
    if existing_content:
        return existing_content

    # Validate that the uploaded bytes are actually a readable PDF.
    try:
        from io import BytesIO
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))

        if reader.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Encrypted PDFs are not supported",
            )

        # Force page access so corrupt PDFs are detected.
        len(reader.pages)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PDF: {exc}",
        )

    original_filename = file.filename
    safe_filename = sanitize_filename(original_filename)

    # UUID prevents collisions and path traversal.
    stored_filename = (
        f"{uuid.uuid4().hex}_{safe_filename}"
    )

    STORAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = STORAGE_DIR / stored_filename

    file_path.write_bytes(content)

    try:
        document_data = DocumentCreate(
            filename=original_filename,
            stored_filename=stored_filename,
            file_size=len(content),
            content_type="application/pdf",
            status="uploaded",
        )

        document = create_document(
            db,
            document_data,
            current_user.id,
            str(file_path),
            idempotency_key=idempotency_key,
            content_sha256=content_sha256,
        )

        # Start PDF ingestion after the response is prepared.
        background_tasks.add_task(
            ingest_document_background,
            document.id,
            current_user.id,
        )

        return document

    except IntegrityError:
        db.rollback()
        existing_query = db.query(Document).filter(
            Document.user_id == current_user.id,
        )
        existing = None
        if idempotency_key:
            existing = existing_query.filter(
                Document.idempotency_key == idempotency_key,
            ).first()
        if existing is None:
            existing = db.query(Document).filter(
                Document.user_id == current_user.id,
                Document.content_sha256 == content_sha256,
            ).first()
        if existing:
            if file_path.exists():
                file_path.unlink()
            return existing
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This upload conflicts with an existing document operation. Retry with the same Idempotency-Key.",
        )
    except Exception:
        if file_path.exists():
            file_path.unlink()
        raise


@router.get(
    "/",
    response_model=List[DocumentResponse],
)
def list_documents(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_documents(
        db,
        current_user.id,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document_route(
    document_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_document(
        db,
        document_id,
        current_user.id,
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
)
def get_document_status_route(
    document_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_document_status(
        db,
        document_id,
        current_user.id,
    )


@router.get(
    "/{document_id}/file",
    response_class=FileResponse,
)
def get_document_file_route(
    document_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve a user's own PDF for authenticated citation viewing."""
    document = get_document(db, document_id, current_user.id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = Path(document.file_path)
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file is no longer available",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=Path(document.filename).name,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete(
    "/{document_id}",
    response_model=bool,
)
def delete_document_route(
    document_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_document(
        db,
        document_id,
        current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = Path(document.file_path)

    result = delete_document(
        db,
        document_id,
        current_user.id,
    )

    if file_path.exists():
        file_path.unlink()

    return result
