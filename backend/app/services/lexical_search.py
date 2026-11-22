"""Persistent, tenant-scoped BM25 keyword search using SQLite FTS5."""

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from backend.app.settings import settings


def index_path() -> Path:
    """Keep the lexical index alongside the configured persistent Chroma storage."""
    chroma_path = Path(settings.CHROMA_PERSIST_DIRECTORY).expanduser().resolve()
    return chroma_path.parent / "lexical_index.sqlite3"


def _connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or index_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(target), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def initialize_lexical_index(path: Path | None = None) -> None:
    """Create the FTS5 index and its tenant/document lookup indexes."""
    with _connect(path) as connection:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS lexical_chunks
            USING fts5(
                content,
                user_id UNINDEXED,
                document_id UNINDEXED,
                metadata UNINDEXED,
                tokenize='unicode61'
            )
            """
        )


def replace_document_chunks(
    document_id: int,
    user_id: int,
    chunks: list[Any],
    path: Path | None = None,
) -> int:
    """Atomically replace all lexical chunks belonging to one user's document."""
    if document_id <= 0 or user_id <= 0:
        raise ValueError("Document and user IDs must be positive")

    rows = []
    for chunk in chunks:
        content = str(getattr(chunk, "page_content", "") or "").strip()
        if not content:
            continue

        metadata = dict(getattr(chunk, "metadata", {}) or {})
        if int(metadata.get("document_id", -1)) != document_id:
            raise ValueError("Chunk document ownership mismatch")
        if int(metadata.get("user_id", -1)) != user_id:
            raise ValueError("Chunk user ownership mismatch")

        rows.append((
            content,
            str(user_id),
            str(document_id),
            json.dumps(metadata, ensure_ascii=False, default=str),
        ))

    initialize_lexical_index(path)

    with _connect(path) as connection:
        connection.execute(
            """
            DELETE FROM lexical_chunks
            WHERE user_id = ? AND document_id = ?
            """,
            (str(user_id), str(document_id)),
        )
        connection.executemany(
            """
            INSERT INTO lexical_chunks
                (content, user_id, document_id, metadata)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )

    return len(rows)


def delete_document_chunks(
    document_id: int,
    user_id: int,
    path: Path | None = None,
) -> int:
    """Delete only the specified owner's lexical entries for a document."""
    if document_id <= 0 or user_id <= 0:
        raise ValueError("Document and user IDs must be positive")

    initialize_lexical_index(path)

    with _connect(path) as connection:
        cursor = connection.execute(
            """
            DELETE FROM lexical_chunks
            WHERE user_id = ? AND document_id = ?
            """,
            (str(user_id), str(document_id)),
        )
        return cursor.rowcount


def _build_match_query(query: str) -> str:
    """Convert ordinary user text into a safe FTS5 OR expression."""
    tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
    tokens = list(dict.fromkeys(token.lower() for token in tokens if len(token) > 1))
    if not tokens:
        return ""

    # Quote every token so FTS operators supplied by users cannot alter the query.
    return " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens[:32])


def keyword_search(
    query: str,
    user_id: int,
    k: int = 10,
    document_ids: list[int] | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return tenant-scoped BM25 results with their original source metadata."""
    if user_id <= 0:
        raise ValueError("User ID must be positive")

    limit = max(1, min(int(k), 100))
    match_query = _build_match_query(query)
    if not match_query:
        return []

    initialize_lexical_index(path)

    sql = """
        SELECT content, metadata, document_id, bm25(lexical_chunks) AS score
        FROM lexical_chunks
        WHERE lexical_chunks MATCH ?
          AND user_id = ?
    """
    parameters: list[Any] = [match_query, str(user_id)]

    if document_ids is not None:
        allowed_ids = sorted({int(value) for value in document_ids if int(value) > 0})
        if not allowed_ids:
            return []
        placeholders = ",".join("?" for _ in allowed_ids)
        sql += f" AND document_id IN ({placeholders})"
        parameters.extend(str(value) for value in allowed_ids)

    sql += " ORDER BY score ASC LIMIT ?"
    parameters.append(limit)

    with _connect(path) as connection:
        rows = connection.execute(sql, parameters).fetchall()

    results = []
    for row in rows:
        try:
            metadata = json.loads(row["metadata"])
        except (TypeError, json.JSONDecodeError):
            metadata = {}

        results.append({
            "content": row["content"],
            "metadata": metadata,
            "document_id": int(row["document_id"]),
            "score": float(row["score"]),
        })

    return results
