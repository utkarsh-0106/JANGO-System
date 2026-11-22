from types import SimpleNamespace

from chromadb.errors import NotFoundError
from langchain_core.documents import Document as LangChainDocument

from backend.app.services.lexical_backfill import backfill_chroma_to_lexical
from backend.app.services.lexical_search import (
    keyword_search,
    replace_document_chunks,
)


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def count(self):
        return len(self.records)

    def get(self, limit=None, offset=0, where=None, include=None):
        records = self.records

        if where:
            conditions = where.get("$and", [])
            for condition in conditions:
                key, value = next(iter(condition.items()))
                records = [
                    row for row in records
                    if (row["metadata"] or {}).get(key) == value
                ]

        if limit is not None:
            records = records[offset:offset + limit]

        result = {}
        if include is None or "metadatas" in include:
            result["metadatas"] = [row["metadata"] for row in records]
        if include is None or "documents" in include:
            result["documents"] = [row["document"] for row in records]
        return result


class FakeClient:
    def __init__(self, collection=None):
        self.collection = collection

    def get_collection(self, name):
        if self.collection is None:
            raise NotFoundError("Collection does not exist")
        return self.collection


def record(text, user_id=7, document_id=101, **extra):
    return {
        "document": text,
        "metadata": {
            "user_id": user_id,
            "document_id": document_id,
            "filename": "policy.pdf",
            "page_number": 2,
            **extra,
        },
    }


def test_missing_collection_is_a_safe_noop(tmp_path):
    report = backfill_chroma_to_lexical(
        lexical_path=tmp_path / "lexical.sqlite3",
        client=FakeClient(),
    )

    assert report["collection_missing"] is True
    assert report["documents_indexed"] == 0
    assert report["failed_documents"] == 0


def test_backfill_indexes_complete_documents_and_preserves_metadata(tmp_path):
    path = tmp_path / "lexical.sqlite3"
    client = FakeClient(FakeCollection([
        record("Annual leave policy requires manager approval."),
        record("Employees receive twenty days of annual leave."),
        record("Payroll is processed monthly.", user_id=8, document_id=202),
    ]))

    report = backfill_chroma_to_lexical(
        lexical_path=path,
        batch_size=1,
        client=client,
    )

    assert report["vectors_scanned"] == 3
    assert report["documents_indexed"] == 2
    assert report["chunks_indexed"] == 3
    assert report["failed_documents"] == 0

    results = keyword_search("annual leave", 7, path=path)
    assert len(results) == 2
    assert all(row["metadata"]["filename"] == "policy.pdf" for row in results)
    assert keyword_search("payroll", 7, path=path) == []
    assert len(keyword_search("payroll", 8, path=path)) == 1


def test_backfill_is_idempotent(tmp_path):
    path = tmp_path / "lexical.sqlite3"
    client = FakeClient(FakeCollection([
        record("Original policy text."),
        record("Additional policy section."),
    ]))

    first = backfill_chroma_to_lexical(lexical_path=path, client=client)
    second = backfill_chroma_to_lexical(lexical_path=path, client=client)

    assert first["chunks_indexed"] == 2
    assert second["chunks_indexed"] == 2
    assert len(keyword_search("policy", 7, path=path)) == 2


def test_invalid_metadata_is_skipped_without_creating_an_owner(tmp_path):
    path = tmp_path / "lexical.sqlite3"
    client = FakeClient(FakeCollection([
        record("Valid document content."),
        record("Invalid owner content.", user_id=None, document_id=303),
    ]))

    report = backfill_chroma_to_lexical(lexical_path=path, client=client)

    assert report["documents_indexed"] == 1
    assert report["invalid_records"] == 1
    assert keyword_search("invalid owner", 303, path=path) == []


def test_failed_document_does_not_stop_other_documents(tmp_path, monkeypatch):
    path = tmp_path / "lexical.sqlite3"
    client = FakeClient(FakeCollection([
        record("Firstonly policy content.", document_id=101),
        record("Secondonly policy content.", document_id=202),
    ]))

    from backend.app.services import lexical_backfill

    original = lexical_backfill.replace_document_chunks

    def fail_first(document_id, user_id, chunks, path=None):
        if document_id == 101:
            raise RuntimeError("simulated failure")
        return original(document_id, user_id, chunks, path)

    monkeypatch.setattr(lexical_backfill, "replace_document_chunks", fail_first)

    report = backfill_chroma_to_lexical(lexical_path=path, client=client)

    assert report["failed_documents"] == 1
    assert report["documents_indexed"] == 1
    assert keyword_search("secondonly", 7, path=path)
    assert keyword_search("firstonly", 7, path=path) == []



def test_invalid_owner_record_prevents_partial_document_backfill(tmp_path):
    path = tmp_path / "lexical.sqlite3"

    # Simulate an older, valid lexical entry that must not be erased.
    replace_document_chunks(
        document_id=101,
        user_id=7,
        chunks=[
            LangChainDocument(
                page_content="Existingmarker legacy indexed content.",
                metadata={"user_id": 7, "document_id": 101},
            )
        ],
        path=path,
    )

    client = FakeClient(FakeCollection([
        record("Newmarker valid chunk.", user_id=7, document_id=101),
        record("Malformed owner chunk.", user_id=None, document_id=101),
        record("Independent valid document.", user_id=8, document_id=202),
    ]))

    report = backfill_chroma_to_lexical(
        lexical_path=path,
        batch_size=1,
        client=client,
    )

    assert report["invalid_records"] == 1
    assert report["documents_indexed"] == 1
    assert keyword_search("existingmarker", 7, path=path)
    assert keyword_search("newmarker", 7, path=path) == []
    assert keyword_search("independent", 8, path=path)


def test_custom_chroma_path_uses_sibling_lexical_database(tmp_path):
    chroma_path = tmp_path / "custom_chroma"
    lexical_path = tmp_path / "lexical_index.sqlite3"

    client = FakeClient(FakeCollection([
        record("Custompath unique marker content."),
    ]))

    report = backfill_chroma_to_lexical(
        persist_directory=chroma_path,
        client=client,
    )

    assert report["lexical_index_path"] == str(lexical_path.resolve())
    assert len(keyword_search("custompath", 7, path=lexical_path)) == 1


def test_backfill_does_not_modify_source_chroma_records(tmp_path):
    import copy

    source_records = [
        record("Original Chroma source marker.", document_id=101),
        record("Another original source marker.", user_id=8, document_id=202),
    ]
    original_records = copy.deepcopy(source_records)
    client = FakeClient(FakeCollection(source_records))

    backfill_chroma_to_lexical(
        lexical_path=tmp_path / "lexical.sqlite3",
        client=client,
    )

    assert client.collection.records == original_records
