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
    ) as add_chunks, patch.object(
        ingestion,
        "replace_document_chunks",
    ) as replace_lexical:

        result = ingestion.ingest_document(
            document_id=123,
            db=db,
            user_id=7,
        )

    assert result is True
    assert document.status == "ready"

    chunks = add_chunks.call_args.args[0]

    assert len(chunks) >= 2
    replace_lexical.assert_called_once_with(123, 7, chunks)

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

def test_ingestion_rejects_unsupported_format(tmp_path):
    unsupported = tmp_path / "test.unsupported"
    unsupported.write_text("This is an unsupported file.")

    document = MagicMock()
    document.id = 123
    document.user_id = 7
    document.filename = "test.unsupported"
    document.file_path = str(unsupported)
    document.content_type = "application/octet-stream"

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
    assert "Unsupported file format" in document.processing_error

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

    with (
        patch.object(vector_store, "get_vector_store", return_value=fake_store),
        patch.object(vector_store, "embedding_identity", return_value=("gemini", "embedding-v2")),
    ):
        vector_store.similarity_search(query="company policy", user_id=42, k=5)

    fake_store.similarity_search_with_score.assert_called_once_with(
        "company policy", k=5, filter={"$and": [
            {"user_id": 42},
            {"embedding_provider": "gemini"},
            {"embedding_model": "embedding-v2"},
        ]},
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


def test_rag_retries_transient_ai_failure():
    request = RagRequest(question="What is the policy?")

    retrieved_documents = [
        (
            LangChainDocument(
                page_content="The policy allows 20 days of leave.",
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

    first_failure = RuntimeError("503 UNAVAILABLE: high demand")
    fake_response = MagicMock()
    fake_response.content = "The policy allows 20 days of leave."
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = fake_response

    with patch.object(
        rag,
        "similarity_search",
        return_value=retrieved_documents,
    ), patch.object(
        rag,
        "_get_llm",
        side_effect=[first_failure, fake_llm],
    ) as get_llm, patch.object(
        rag.settings,
        "GEMINI_FALLBACK_MODELS",
        "",
    ), patch.object(
        rag.settings,
        "AI_MAX_ATTEMPTS",
        2,
    ):
        response = rag.query_rag(request, user_id=1)

    assert response.answer == "The policy allows 20 days of leave."
    assert get_llm.call_count == 2


def test_transient_error_detector():
    assert rag._is_transient_ai_error(RuntimeError("503 UNAVAILABLE")) is True
    assert rag._is_transient_ai_error(RuntimeError("429 rate limit")) is True
    assert rag._is_transient_ai_error(RuntimeError("invalid API key")) is False


def test_rag_request_accepts_response_language():
    assert RagRequest(question="नमस्ते", response_language="hindi").response_language == "hindi"
    assert RagRequest(question="What is RAG?", response_language="english").response_language == "english"
    assert RagRequest(question="RAG kya hai?", response_language="hinglish").response_language == "hinglish"
    assert RagRequest(question="Hello").response_language == "auto"


def test_rag_request_rejects_unsupported_response_language():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RagRequest(question="Hello", response_language="french")



def test_reciprocal_rank_fusion_merges_and_deduplicates_results():
    semantic_doc = LangChainDocument(
        page_content="Employees receive 20 days of annual leave.",
        metadata={"document_id": 10, "user_id": 5, "filename": "policy.pdf", "page_number": 3},
    )
    semantic_only_doc = LangChainDocument(
        page_content="Annual leave requests need manager approval.",
        metadata={"document_id": 11, "user_id": 5, "filename": "handbook.pdf", "page_number": 8},
    )

    lexical_results = [
        {
            "content": "Employees receive 20 days of annual leave.",
            "metadata": {"document_id": 10, "user_id": 5, "filename": "policy.pdf", "page_number": 3},
            "score": -2.5,
        },
        {
            "content": "Annual leave balance is updated monthly.",
            "metadata": {"document_id": 12, "user_id": 5, "filename": "benefits.pdf", "page_number": 2},
            "score": -1.8,
        },
    ]

    fused = rag._reciprocal_rank_fusion(
        semantic_results=[(semantic_doc, 0.12), (semantic_only_doc, 0.2)],
        lexical_results=lexical_results,
        limit=5,
    )

    assert len(fused) == 3
    assert fused[0][0].metadata["document_id"] == 10
    assert fused[0][0].page_content == semantic_doc.page_content
    assert fused[0][1] > fused[1][1]
    assert {item[0].metadata["document_id"] for item in fused} == {10, 11, 12}


def test_reciprocal_rank_fusion_respects_result_limit():
    documents = [
        (
            LangChainDocument(
                page_content=f"Unique content {index}",
                metadata={"document_id": index, "user_id": 1},
            ),
            0.1,
        )
        for index in range(1, 5)
    ]

    fused = rag._reciprocal_rank_fusion(
        semantic_results=documents,
        lexical_results=[],
        limit=2,
    )

    assert len(fused) == 2


def test_rag_uses_lexical_results_when_semantic_search_fails():
    request = RagRequest(question="What is the leave policy?")
    lexical_result = {
        "content": "Employees receive 20 days of annual leave.",
        "metadata": {
            "document_id": 10,
            "user_id": 5,
            "filename": "employee_policy.pdf",
            "page_number": 3,
        },
        "score": -2.0,
    }

    fake_response = Mock()
    fake_response.content = "Employees receive 20 days of annual leave."
    fake_llm = Mock()
    fake_llm.invoke.return_value = fake_response

    with patch.object(
        rag,
        "similarity_search",
        side_effect=RuntimeError("Chroma temporarily unavailable"),
    ), patch.object(
        rag,
        "keyword_search",
        return_value=[lexical_result],
    ) as lexical_search, patch.object(
        rag,
        "_get_llm",
        return_value=fake_llm,
    ):
        response = rag.query_rag(request, user_id=5)

    assert response.answer == "Employees receive 20 days of annual leave."
    assert len(response.sources) == 1
    assert response.sources[0]["filename"] == "employee_policy.pdf"
    assert response.sources[0]["page_number"] == 3
    lexical_search.assert_called_once_with(
        query="What is the leave policy?",
        user_id=5,
        k=5,
    )


def test_rag_uses_semantic_results_when_lexical_search_fails():
    request = RagRequest(question="What is the leave policy?")
    semantic_result = [
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

    fake_response = Mock()
    fake_response.content = "Employees receive 20 days of annual leave."
    fake_llm = Mock()
    fake_llm.invoke.return_value = fake_response

    with patch.object(
        rag,
        "similarity_search",
        return_value=semantic_result,
    ), patch.object(
        rag,
        "keyword_search",
        side_effect=RuntimeError("FTS index temporarily unavailable"),
    ), patch.object(
        rag,
        "_get_llm",
        return_value=fake_llm,
    ):
        response = rag.query_rag(request, user_id=5)

    assert response.answer == "Employees receive 20 days of annual leave."
    assert len(response.sources) == 1
    assert response.sources[0]["filename"] == "employee_policy.pdf"


def test_rag_returns_503_and_logs_both_retrieval_failures(caplog):
    caplog.set_level("INFO")
    request = RagRequest(question="What is the leave policy?")

    with patch.object(
        rag,
        "similarity_search",
        side_effect=RuntimeError("Chroma unavailable"),
    ), patch.object(
        rag,
        "keyword_search",
        side_effect=OSError("Lexical index unavailable"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            rag.query_rag(request, user_id=5)

    assert exc_info.value.status_code == 503
    assert isinstance(exc_info.value.__cause__, RuntimeError)

    failure_records = [
        record for record in caplog.records
        if "document_retrieval_failed" in record.message
    ]

    assert len(failure_records) == 1
    assert failure_records[0].exc_info is None
    assert "RuntimeError" in failure_records[0].message
    assert "OSError" in failure_records[0].message

    metric_records = [
        record for record in caplog.records
        if "document_retrieval_complete" in record.message
    ]
    assert len(metric_records) == 1
    assert "semantic_status=error" in metric_records[0].message
    assert "lexical_status=error" in metric_records[0].message
    assert "fused_count=0" in metric_records[0].message


def test_rag_logs_retrieval_metrics_without_document_content(caplog):
    caplog.set_level("INFO")
    request = RagRequest(question="What is the leave policy?")

    with patch.object(
        rag,
        "similarity_search",
        return_value=[],
    ), patch.object(
        rag,
        "keyword_search",
        return_value=[],
    ):
        response = rag.query_rag(request, user_id=5)

    assert response.sources == []

    metric_records = [
        record for record in caplog.records
        if "document_retrieval_complete" in record.message
    ]

    assert len(metric_records) == 1
    message = metric_records[0].message

    assert "user_id=5" in message
    assert "semantic_count=0" in message
    assert "lexical_count=0" in message
    assert "fused_count=0" in message
    assert "semantic_latency_ms=" in message
    assert "lexical_latency_ms=" in message
    assert "fusion_latency_ms=" in message
    assert "total_latency_ms=" in message
    assert "What is the leave policy?" not in message
