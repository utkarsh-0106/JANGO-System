from pathlib import Path
from functools import lru_cache
from threading import RLock
from typing import Iterable

from langchain_chroma import Chroma
from langchain_core.documents import Document as LangChainDocument

from backend.app.services.ai_config import (
    AIProviderConfigError,
    normalize_provider,
    require_gemini_api_key,
)
from backend.app.settings import settings

COLLECTION_NAME = "enterprise_documents"
_CHROMA_LOCK = RLock()


class ChromaDefaultEmbeddings:
    """Adapter for Chroma's native local embedding function."""

    def __init__(self):
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        self._embedding_function = DefaultEmbeddingFunction()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._embedding_function(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self._embedding_function([text])[0].tolist()


def _get_embeddings():
    provider = normalize_provider(settings.EMBEDDING_PROVIDER)

    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=require_gemini_api_key(),
        )

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )

    if provider == "chroma":
        return ChromaDefaultEmbeddings()

    raise AIProviderConfigError(
        f"Unsupported EMBEDDING_PROVIDER '{settings.EMBEDDING_PROVIDER}'. "
        "Use 'gemini', 'ollama', or 'chroma'."
    )


def get_embeddings():
    return _get_embeddings()


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    persist_path = Path(settings.CHROMA_PERSIST_DIRECTORY).resolve()
    persist_path.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_path),
        embedding_function=get_embeddings(),
    )


def add_chunks(chunks: Iterable[LangChainDocument]) -> list[str]:
    chunks = list(chunks)
    if not chunks:
        return []
    with _CHROMA_LOCK:
        return get_vector_store().add_documents(chunks)


def delete_document_vectors(document_id: int) -> None:
    with _CHROMA_LOCK:
        collection = get_vector_store()._collection
        result = collection.get(where={"document_id": int(document_id)})
        ids = result.get("ids", [])
        if ids:
            collection.delete(ids=ids)


def similarity_search(query: str, user_id: int, k: int = 5):
    with _CHROMA_LOCK:
        return get_vector_store().similarity_search_with_score(
            query, k=k, filter={"user_id": int(user_id)}
        )
