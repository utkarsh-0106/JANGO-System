from unittest.mock import patch

import pytest

from backend.app.services import rag
from backend.app.services import vector_store
from backend.app.services.ai_config import AIProviderConfigError
from backend.app.settings import Settings


def test_cors_origins_parse_localhost_and_production():
    settings = Settings(
        CORS_ORIGINS="http://localhost:5173,https://example.vercel.app",
        SECRET_KEY="test-secret",
        ENVIRONMENT="development",
    )

    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "https://example.vercel.app",
    ]


def test_cors_origins_default_localhost():
    settings = Settings(
        CORS_ORIGINS="",
        SECRET_KEY="test-secret",
        ENVIRONMENT="development",
    )

    assert settings.cors_origin_list == ["http://localhost:5173"]


def test_ollama_llm_provider_does_not_construct_gemini():
    with (
        patch.object(rag.settings, "LLM_PROVIDER", "ollama"),
        patch.object(rag.settings, "OLLAMA_CHAT_MODEL", "qwen3:8b"),
        patch.object(rag.settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
        patch("langchain_ollama.ChatOllama") as mock_ollama,
        patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_gemini,
    ):
        mock_ollama.return_value = object()
        llm = rag._get_llm()

    mock_ollama.assert_called_once_with(
        model="qwen3:8b",
        base_url="http://localhost:11434",
        temperature=0,
    )
    mock_gemini.assert_not_called()
    assert llm is mock_ollama.return_value


def test_gemini_llm_provider_does_not_construct_ollama():
    with (
        patch.object(rag.settings, "LLM_PROVIDER", "gemini"),
        patch.object(rag.settings, "GEMINI_API_KEY", "fake-gemini-key"),
        patch.object(rag.settings, "GEMINI_CHAT_MODEL", "gemini-2.0-flash"),
        patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_gemini,
        patch("langchain_ollama.ChatOllama") as mock_ollama,
    ):
        mock_gemini.return_value = object()
        llm = rag._get_llm()

    mock_gemini.assert_called_once()
    kwargs = mock_gemini.call_args.kwargs
    assert kwargs["model"] == "gemini-2.0-flash"
    assert kwargs["google_api_key"] == "fake-gemini-key"
    assert kwargs["temperature"] == 0
    mock_ollama.assert_not_called()
    assert llm is mock_gemini.return_value


def test_missing_gemini_api_key_for_llm_fails_clearly():
    with (
        patch.object(rag.settings, "LLM_PROVIDER", "gemini"),
        patch.object(rag.settings, "GEMINI_API_KEY", None),
    ):
        with pytest.raises(AIProviderConfigError, match="GEMINI_API_KEY"):
            rag._get_llm()


def test_ollama_embedding_provider_does_not_construct_gemini():
    with (
        patch.object(vector_store.settings, "EMBEDDING_PROVIDER", "ollama"),
        patch.object(vector_store.settings, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        patch.object(vector_store.settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
        patch("langchain_ollama.OllamaEmbeddings") as mock_ollama,
        patch("langchain_google_genai.GoogleGenerativeAIEmbeddings") as mock_gemini,
    ):
        mock_ollama.return_value = object()
        embeddings = vector_store._get_embeddings()

    mock_ollama.assert_called_once_with(
        model="nomic-embed-text",
        base_url="http://localhost:11434",
    )
    mock_gemini.assert_not_called()
    assert embeddings is mock_ollama.return_value


def test_gemini_embedding_provider_does_not_construct_ollama():
    with (
        patch.object(vector_store.settings, "EMBEDDING_PROVIDER", "gemini"),
        patch.object(vector_store.settings, "GEMINI_API_KEY", "fake-gemini-key"),
        patch.object(
            vector_store.settings,
            "GEMINI_EMBEDDING_MODEL",
            "models/text-embedding-004",
        ),
        patch("langchain_google_genai.GoogleGenerativeAIEmbeddings") as mock_gemini,
        patch("langchain_ollama.OllamaEmbeddings") as mock_ollama,
    ):
        mock_gemini.return_value = object()
        embeddings = vector_store._get_embeddings()

    mock_gemini.assert_called_once()
    kwargs = mock_gemini.call_args.kwargs
    assert kwargs["model"] == "models/text-embedding-004"
    assert kwargs["google_api_key"] == "fake-gemini-key"
    mock_ollama.assert_not_called()
    assert embeddings is mock_gemini.return_value


def test_missing_gemini_api_key_for_embeddings_fails_clearly():
    with (
        patch.object(vector_store.settings, "EMBEDDING_PROVIDER", "gemini"),
        patch.object(vector_store.settings, "GEMINI_API_KEY", ""),
    ):
        with pytest.raises(AIProviderConfigError, match="GEMINI_API_KEY"):
            vector_store._get_embeddings()


def test_unsupported_providers_fail_clearly():
    with patch.object(rag.settings, "LLM_PROVIDER", "openai"):
        with pytest.raises(AIProviderConfigError, match="Unsupported LLM_PROVIDER"):
            rag._get_llm()

    with patch.object(vector_store.settings, "EMBEDDING_PROVIDER", "openai"):
        with pytest.raises(AIProviderConfigError, match="Unsupported EMBEDDING_PROVIDER"):
            vector_store._get_embeddings()
