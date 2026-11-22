"""Safe, idempotent backfill from persistent Chroma records to SQLite FTS5."""

import logging
from pathlib import Path
from typing import Any

import chromadb
from langchain_core.documents import Document as LangChainDocument

from backend.app.services.lexical_search import replace_document_chunks
from backend.app.services.vector_store import COLLECTION_NAME
from backend.app.settings import settings

logger = logging.getLogger(__name__)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def backfill_chroma_to_lexical(
    persist_directory: str | Path | None = None,
    lexical_path: str | Path | None = None,
    batch_size: int = 500,
    client=None,
) -> dict[str, Any]:
    """Copy existing Chroma text into FTS5 without changing Chroma or embeddings.

    Missing collections are treated as an empty source. A document is replaced
    in FTS5 only after all its Chroma records have been fetched and validated.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    path = Path(
        persist_directory or settings.CHROMA_PERSIST_DIRECTORY
    ).expanduser().resolve()

    lexical_target = (
        Path(lexical_path).expanduser().resolve()
        if lexical_path
        else path.parent / "lexical_index.sqlite3"
    )

    report = {
        "collection": COLLECTION_NAME,
        "lexical_index_path": str(lexical_target),
        "collection_missing": False,
        "vectors_scanned": 0,
        "documents_indexed": 0,
        "chunks_indexed": 0,
        "invalid_records": 0,
        "failed_documents": 0,
    }

    if client is None:
        if not path.exists():
            report["collection_missing"] = True
            return report
        client = chromadb.PersistentClient(path=str(path))

    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except chromadb.errors.NotFoundError:
        report["collection_missing"] = True
        return report

    total = collection.count()
    report["vectors_scanned"] = total

    # Discover only validated tenant/document pairs. No embeddings are read.
    document_keys: set[tuple[int, int]] = set()
    invalid_document_ids: set[int] = set()

    for offset in range(0, total, batch_size):
        page = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas"],
        )
        for metadata in page.get("metadatas") or []:
            metadata = metadata or {}
            user_id = _positive_int(metadata.get("user_id"))
            document_id = _positive_int(metadata.get("document_id"))

            if document_id is None:
                report["invalid_records"] += 1
                continue

            if user_id is None:
                report["invalid_records"] += 1
                invalid_document_ids.add(document_id)
                continue

            document_keys.add((user_id, document_id))

    # Fetch each complete document before replacing its lexical entries.
    for user_id, document_id in sorted(document_keys):
        # A malformed record with this document ID makes the entire document unsafe to backfill.
        if document_id in invalid_document_ids:
            continue

        try:
            records = collection.get(
                where={
                    "$and": [
                        {"user_id": user_id},
                        {"document_id": document_id},
                    ]
                },
                include=["documents", "metadatas"],
            )

            texts = records.get("documents") or []
            metadatas = records.get("metadatas") or []

            if len(texts) != len(metadatas):
                raise ValueError("Chroma returned mismatched text and metadata")

            chunks = []
            invalid_document = False

            for content, metadata in zip(texts, metadatas):
                metadata = metadata or {}

                # Fail closed: never mix records from different owners/documents.
                if (
                    _positive_int(metadata.get("user_id")) != user_id
                    or _positive_int(metadata.get("document_id")) != document_id
                    or not isinstance(content, str)
                    or not content.strip()
                ):
                    invalid_document = True
                    break

                chunks.append(
                    LangChainDocument(
                        page_content=content,
                        metadata=dict(metadata),
                    )
                )

            if invalid_document or not chunks:
                report["invalid_records"] += 1
                continue

            indexed = replace_document_chunks(
                document_id=document_id,
                user_id=user_id,
                chunks=chunks,
                path=lexical_target,
            )
            report["documents_indexed"] += 1
            report["chunks_indexed"] += indexed

        except Exception as exc:
            report["failed_documents"] += 1
            logger.error(
                "lexical_backfill_document_failed document_id=%s "
                "user_id=%s error_type=%s",
                document_id,
                user_id,
                type(exc).__name__,
            )

    logger.info(
        "lexical_backfill_completed vectors=%s documents=%s chunks=%s "
        "invalid=%s failed=%s",
        report["vectors_scanned"],
        report["documents_indexed"],
        report["chunks_indexed"],
        report["invalid_records"],
        report["failed_documents"],
    )
    return report
