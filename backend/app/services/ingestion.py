from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from langchain_core.documents import Document as LangChainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy.orm import Session
from backend.app.db import SessionLocal
from backend.app.models import Document
from backend.app.services.documents import get_document
from backend.app.services.vector_store import add_chunks, delete_document_vectors

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def _load_text(file_path: Path, extension: str) -> list[tuple[str, dict[str, Any]]]:
    """Return extracted text units and their source metadata."""
    if extension == ".pdf":
        reader = PdfReader(str(file_path))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")
        return [(page.extract_text() or "", {"page_number": i}) for i, page in enumerate(reader.pages, 1)]

    if extension == ".docx":
        from docx import Document as DocxDocument
        doc = DocxDocument(str(file_path))
        parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table_index, table in enumerate(doc.tables, 1):
            parts.append(f"Table {table_index}:")
            for row in table.rows:
                parts.append(" | ".join(cell.text.replace("\n", " ").strip() for cell in row.cells))
        return [("\n".join(parts), {"section": "document"})]

    if extension in {".txt", ".md", ".log"}:
        return [(file_path.read_text(encoding="utf-8-sig"), {"section": "text"})]

    if extension == ".rtf":
        from striprtf.striprtf import rtf_to_text
        return [(rtf_to_text(file_path.read_text(encoding="utf-8", errors="replace")), {"section": "rtf"})]

    if extension in {".yaml", ".yml"}:
        import yaml
        data = yaml.safe_load(file_path.read_text(encoding="utf-8-sig"))
        return [(json.dumps(data, ensure_ascii=False, indent=2, default=str), {"section": "yaml"})]

    if extension == ".xml":
        root = ET.parse(file_path).getroot()
        return [("\n".join(text.strip() for text in root.itertext() if text and text.strip()), {"section": "xml", "root_tag": root.tag})]

    if extension == ".odt":
        from odf.opendocument import load
        from odf import text as odf_text, teletype
        document = load(str(file_path))
        paragraphs = document.getElementsByType(odf_text.P)
        parts = [teletype.extractText(paragraph).strip() for paragraph in paragraphs]
        return [("\n".join(part for part in parts if part), {"section": "odt"})]

    if extension in {".html", ".htm"}:
        parser = _HTMLTextExtractor()
        parser.feed(file_path.read_text(encoding="utf-8-sig"))
        return [(" ".join(parser.parts), {"section": "html"})]

    if extension == ".json":
        data = json.loads(file_path.read_text(encoding="utf-8-sig"))
        return [(json.dumps(data, ensure_ascii=False, indent=2), {"section": "json"})]

    if extension == ".csv":
        units = []
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV must contain a header row")
            headers = [str(h or f"column_{i+1}") for i, h in enumerate(reader.fieldnames)]
            rows = []
            for row_number, row in enumerate(reader, 2):
                values = [f"{headers[i]}: {row.get(reader.fieldnames[i], '') or ''}" for i in range(len(headers))]
                rows.append(f"Row {row_number}: " + " | ".join(values))
                if len(rows) >= 40:
                    units.append(("\n".join(rows), {"section": "csv_rows", "row_start": row_number - len(rows) + 1, "row_end": row_number, "columns": ", ".join(headers)}))
                    rows = []
            if rows:
                units.append(("\n".join(rows), {"section": "csv_rows", "columns": ", ".join(headers)}))
        if not units:
            units.append(("CSV columns: " + ", ".join(headers) + "\nNo data rows.", {"section": "csv_rows", "columns": ", ".join(headers)}))
        return units

    if extension == ".xls":
        import xlrd
        workbook = xlrd.open_workbook(str(file_path), on_demand=True)
        units = []
        try:
            for sheet in workbook.sheets():
                if sheet.nrows == 0:
                    continue
                headers = [str(sheet.cell_value(0, col) or f"column_{col+1}") for col in range(sheet.ncols)]
                batch = []
                row_start = 2
                for row_index in range(1, sheet.nrows):
                    values = [f"{headers[col]}: {sheet.cell_value(row_index, col)}" for col in range(sheet.ncols)]
                    batch.append(f"Row {row_index + 1}: " + " | ".join(values))
                    if len(batch) >= 40:
                        units.append((f"Worksheet: {sheet.name}\nColumns: {', '.join(headers)}\n" + "\n".join(batch), {"section": "spreadsheet_rows", "sheet_name": sheet.name, "row_start": row_start, "row_end": row_index + 1, "columns": ", ".join(headers)}))
                        batch, row_start = [], row_index + 2
                if batch:
                    units.append((f"Worksheet: {sheet.name}\nColumns: {', '.join(headers)}\n" + "\n".join(batch), {"section": "spreadsheet_rows", "sheet_name": sheet.name, "row_start": row_start, "row_end": row_start + len(batch) - 1, "columns": ", ".join(headers)}))
        finally:
            workbook.release_resources()
        return units or [("Excel workbook contains no readable rows.", {"section": "spreadsheet_rows"})]

    if extension == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(file_path, read_only=True, data_only=True)
        units = []
        try:
            for sheet in workbook.worksheets:
                rows_iter = sheet.iter_rows(values_only=True)
                headers = next(rows_iter, None)
                if not headers:
                    continue
                headers = [str(value if value is not None else f"column_{i+1}") for i, value in enumerate(headers)]
                batch = []
                row_start = 2
                for row_number, row in enumerate(rows_iter, 2):
                    values = [f"{headers[i]}: {row[i] if i < len(row) and row[i] is not None else ''}" for i in range(len(headers))]
                    batch.append(f"Row {row_number}: " + " | ".join(values))
                    if len(batch) >= 40:
                        units.append((f"Worksheet: {sheet.title}\nColumns: {', '.join(headers)}\n" + "\n".join(batch), {"section": "spreadsheet_rows", "sheet_name": sheet.title, "row_start": row_start, "row_end": row_number, "columns": ", ".join(headers)}))
                        batch, row_start = [], row_number + 1
                if batch:
                    units.append((f"Worksheet: {sheet.title}\nColumns: {', '.join(headers)}\n" + "\n".join(batch), {"section": "spreadsheet_rows", "sheet_name": sheet.title, "row_start": row_start, "row_end": row_start + len(batch) - 1, "columns": ", ".join(headers)}))
        finally:
            workbook.close()
        return units

    if extension == ".pptx":
        from pptx import Presentation
        presentation = Presentation(str(file_path))
        units = []
        for slide_number, slide in enumerate(presentation.slides, 1):
            parts = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False) and shape.text.strip():
                    parts.append(shape.text.strip())
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        parts.append(" | ".join(cell.text.strip().replace("\n", " ") for cell in row.cells))
            if parts:
                units.append(("\n".join(parts), {"section": "slide", "slide_number": slide_number}))
        return units

    raise ValueError(f"Unsupported file extension: {extension}")


def ingest_document(document_id: int, db: Session, user_id: int) -> bool:
    document = get_document(db, document_id, user_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    file_path = Path(document.file_path)
    if not file_path.exists():
        document.status = "failed"
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found")

    try:
        document.status = "processing"
        db.commit()
        delete_document_vectors(document.id)
        extension = Path(document.filename).suffix.lower()
        units = _load_text(file_path, extension)
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks: list[LangChainDocument] = []
        for text, source_metadata in units:
            text = text.strip()
            if not text:
                continue
            for chunk in splitter.split_text(text):
                chunks.append(LangChainDocument(page_content=chunk, metadata={
                    "document_id": int(document.id), "user_id": int(document.user_id),
                    "filename": document.filename, **source_metadata,
                }))
        if not chunks:
            raise ValueError("No extractable text was found in this file")
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Document ingestion failed: {exc}") from exc


def reprocess_document(document_id: int, db: Session, user_id: int) -> bool:
    return ingest_document(document_id=document_id, db=db, user_id=user_id)


def ingest_document_background(document_id: int, user_id: int) -> None:
    db = SessionLocal()
    try:
        ingest_document(document_id=document_id, db=db, user_id=user_id)
    finally:
        db.close()
