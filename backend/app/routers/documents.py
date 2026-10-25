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
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".odt", ".txt", ".md", ".log", ".rtf", ".csv", ".xlsx", ".xls", ".json", ".yaml", ".yml", ".xml", ".html", ".htm"}
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".log": "text/plain",
    ".rtf": "application/rtf",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".xml": "application/xml",
    ".html": "text/html",
    ".htm": "text/html",
}


def sanitize_filename(filename: str) -> str:
    filename = Path(filename or "document").name
    return re.sub(r"[^A-Za-z0-9_.-]", "_", filename)


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

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Supported formats: PDF, DOCX, PPTX, ODT, TXT, MD, LOG, RTF, CSV, XLSX, XLS, JSON, YAML, XML, and HTML.",
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

    # Validate the format before storing it. File extensions are allow-listed above;
    # parsers below validate the actual content for formats with structured containers.
    try:
        from io import BytesIO
        if extension == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise HTTPException(status_code=400, detail="Encrypted PDFs are not supported")
            len(reader.pages)
        elif extension == ".docx":
            from docx import Document as DocxDocument
            DocxDocument(BytesIO(content))
        elif extension == ".xlsx":
            from openpyxl import load_workbook
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            workbook.close()
        elif extension == ".xls":
            import xlrd
            workbook = xlrd.open_workbook(file_contents=content, on_demand=True)
            workbook.release_resources()
        elif extension == ".pptx":
            from pptx import Presentation
            Presentation(BytesIO(content))
        elif extension == ".odt":
            from odf.opendocument import load
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".odt") as temporary:
                temporary.write(content)
                temporary.flush()
                load(temporary.name)
        elif extension == ".json":
            import json
            json.loads(content.decode("utf-8-sig"))
        elif extension in {".yaml", ".yml"}:
            import yaml
            yaml.safe_load(content.decode("utf-8-sig"))
        elif extension == ".xml":
            import xml.etree.ElementTree as ET
            ET.fromstring(content)
        elif extension == ".rtf":
            content.decode("utf-8", errors="replace")
        elif extension in {".txt", ".md", ".log", ".csv", ".html", ".htm"}:
            content.decode("utf-8-sig")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {extension.lstrip('.').upper()} file or unsupported encoding: {exc}",
        ) from exc

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
            content_type=CONTENT_TYPES[extension],
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

        # Start format-aware ingestion after the response is prepared.
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
    """Serve a user's own uploaded file for authenticated access."""
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
        media_type=document.content_type or "application/octet-stream",
        filename=Path(document.filename).name,
        content_disposition_type="inline" if (document.content_type or "").startswith("application/pdf") else "attachment",
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
