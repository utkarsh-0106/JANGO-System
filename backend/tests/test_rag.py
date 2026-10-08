from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from langchain_core.documents import Document as LangChainDocument

from backend.app.schemas.rag import RagRequest
from backend.app.services import ingestion
from backend.app.services import rag
from backend.app.services import vector_store


def test_chunk_configuration():
    assert ingestion.CHUNK_SIZE == 1000
    assert ingestion.CHUNK_OVERLAP == 200
    assert ingestion.CHUNK_OVERLAP < ingestion.CHUNK_SIZE


def test_ingestion_extracts_pages_and_metadata(tmp_path):
    pdf_path = tmp_path / "sample.pdf"

    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(pdf_path))
    pdf.drawString(100, 750, "This is page one content.")
    pdf.showPage()
    pdf.drawString(100, 750, "This is page two content.")
    pdf.save()

    document = MagicMock()
    document.id = 123
    document.user_id = 7
    document.filename = "sample.pdf"
    document.file_path = str(pdf_path)
    document.content_type = "application/pdf"
    document.status = "uploaded"

    db = MagicMock()

    with patch.object(
        ingestion,
        "get_document",
        return_value=document,
    ), patch.object(
        ingestion,
        "delete_document_vectors",
    ), patch.object(
        ingestion,
        "add_chunks",
        return_value=["1", "2"],
    ) as add_chunks:

        result = ingestion.ingest_document(
            document_id=123,
            db=db,
            user_id=7,
        )

    assert result is True
    assert document.status == "ready"

    chunks = add_chunks.call_args.args[0]

    assert len(chunks) >= 2

    for chunk in chunks:
        assert chunk.metadata["document_id"] == 123
        assert chunk.metadata["user_id"] == 7
        assert chunk.metadata["filename"] == "sample.pdf"
        assert "page_number" in chunk.metadata


def test_ingestion_rejects_missing_file(tmp_path):
    document = MagicMock()
    document.id = 123
    document.user_id = 7
    document.filename = "missing.pdf"
    document.file_path = str(tmp_path / "does-not-exist.pdf")
    document.content_type = "application/pdf"

    db = MagicMock()

    with patch.object(
        ingestion,
        "get_document",
        return_value=document,
    ):
        with pytest.raises(HTTPException) as exc:
            ingestion.ingest_document(
                document_id=123,
                db=db,
                user_id=7,
            )

    assert exc.value.status_code == 404
    assert document.status == "failed"


def test_ingestion_rejects_non_pdf(tmp_path):
    non_pdf = tmp_path / "test.txt"
    non_pdf.write_text("This is not a PDF.")

    document = MagicMock()
    document.id = 123
    document.user_id = 7
    document.filename = "test.txt"
    document.file_path = str(non_pdf)
    document.content_type = "text/plain"

    db = MagicMock()

    with patch.object(
        ingestion,
        "get_document",
        return_value=document,
    ):
        with pytest.raises(HTTPException) as exc:
            ingestion.ingest_document(
                document_id=123,
                db=db,
                user_id=7,
            )

    assert exc.value.status_code == 400
    assert document.status == "failed"

def test_vector_store_add_chunks():
    fake_store = MagicMock()
    fake_store.add_documents.return_value = ["id1", "id2"]

    chunks = [
        LangChainDocument(
            page_content="Hello",
            metadata={
                "document_id": 1,
                "user_id": 10,
                "filename": "a.pdf",
                "page_number": 1,
            },
        ),
        LangChainDocument(
            page_content="World",
            metadata={
                "document_id": 1,
                "user_id": 10,
                "filename": "a.pdf",
                "page_number": 1,
            },
        ),
    ]

    with patch.object(
        vector_store,
        "get_vector_store",
        return_value=fake_store,
    ):
        ids = vector_store.add_chunks(chunks)

    assert ids == ["id1", "id2"]
    fake_store.add_documents.assert_called_once()


def test_similarity_search_enforces_user_filter():
    fake_store = MagicMock()
    fake_store.similarity_search_with_score.return_value = []

    with patch.object(
        vector_store,
        "get_vector_store",
        return_value=fake_store,
    ):
        vector_store.similarity_search(
            query="company policy",
            user_id=42,
            k=5,
        )

    fake_store.similarity_search_with_score.assert_called_once_with(
        "company policy",
        k=5,
        filter={"user_id": 42},
    )


def test_rag_rejects_empty_question():
    request = RagRequest(question="   ")

    with pytest.raises(HTTPException) as exc:
        rag.query_rag(request, user_id=1)

    assert exc.value.status_code == 400


def test_rag_uses_local_ollama():
    request = RagRequest(question="What is the policy?")

    retrieved_documents = [
        (
            LangChainDocument(
                page_content="Company policy information.",
                metadata={
                    "document_id": 1,
                    "user_id": 1,
                    "filename": "policy.pdf",
                    "page_number": 1,
                },
            ),
            0.1,
        )
    ]

    fake_llm = Mock()
    fake_response = Mock()
    fake_response.content = "The company policy is described in policy.pdf."
    fake_llm.invoke.return_value = fake_response

    with patch.object(
        rag,
        "similarity_search",
        return_value=retrieved_documents,
    ), patch.object(
        rag,
        "_get_llm",
        return_value=fake_llm,
    ):
        response = rag.query_rag(request, user_id=1)

    assert response.answer == "The company policy is described in policy.pdf."
    assert len(response.sources) == 1
    assert response.sources[0]["filename"] == "policy.pdf"
    assert response.sources[0]["page_number"] == 1
def test_rag_returns_grounded_answer_and_sources():
    request = RagRequest(
        question="What is the leave policy?",
        top_k=2,
    )

    retrieved_documents = [
        (
            LangChainDocument(
                page_content="Employees receive 20 days of annual leave.",
                metadata={
                    "document_id": 10,
                    "user_id": 5,
                    "filename": "employee_policy.pdf",
                    "page_number": 3,
                },
            ),
            0.12,
        )
    ]

    fake_response = MagicMock()
    fake_response.content = (
        "Employees receive 20 days of annual leave. "
        "Source: employee_policy.pdf, page 3."
    )

    fake_llm = MagicMock()
    fake_llm.invoke.return_value = fake_response

    with patch.object(
        rag,
        "similarity_search",
        return_value=retrieved_documents,
    ) as search, patch.object(
        rag,
        "_get_llm",
        return_value=fake_llm,
    ):
        response = rag.query_rag(
            request,
            user_id=5,
        )

    assert response.answer.startswith(
        "Employees receive 20 days"
    )

    assert len(response.sources) == 1

    source = response.sources[0]

    assert source["id"] == 10
    assert source["filename"] == "employee_policy.pdf"
    assert source["page_number"] == 3
    assert source["content"] == (
        "Employees receive 20 days of annual leave."
    )

    search.assert_called_once_with(
        query="What is the leave policy?",
        user_id=5,
        k=2,
    )


def test_rag_returns_unknown_when_no_documents():
    request = RagRequest(
        question="What is the leave policy?"
    )

    with patch.object(
        rag,
        "similarity_search",
        return_value=[],
    ):
        response = rag.query_rag(
            request,
            user_id=99,
        )

    assert response.answer == (
        "I don't know based on the uploaded documents."
    )
    assert response.sources == []
