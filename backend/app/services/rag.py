from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session
from langchain_core.prompts import ChatPromptTemplate

from backend.app.schemas.rag import RagRequest, RagResponse
from backend.app.services.ai_config import (
    AIProviderConfigError,
    normalize_provider,
    require_anthropic_api_key,
    require_gemini_api_key,
    require_groq_api_key,
)
from backend.app.services.vector_store import similarity_search
from backend.app.services.ai_usage import (
    calculate_cost_usd,
    extract_token_usage,
    record_usage,
)
from backend.app.settings import settings


_TRANSIENT_ERROR_MARKERS = (
    "503",
    "502",
    "500",
    "504",
    "429",
    "unavailable",
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "too many requests",
    "overloaded",
    "high demand",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "deadline exceeded",
)


def _is_transient_ai_error(exc: Exception) -> bool:
    """Return True for provider failures that are safe to retry/fail over."""
    text = str(exc).lower()
    return any(marker in text for marker in _TRANSIENT_ERROR_MARKERS)


def _csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _get_llm(provider: str | None = None, model: str | None = None):
    provider = normalize_provider(provider or settings.LLM_PROVIDER)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # Gemini 3.x no longer needs the legacy temperature parameter.
        kwargs: dict[str, Any] = {
            "model": model or settings.GEMINI_CHAT_MODEL,
            "google_api_key": require_gemini_api_key(),
            "timeout": 45,
            "max_retries": 0,
        }
        return ChatGoogleGenerativeAI(**kwargs)

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model or settings.GROQ_CHAT_MODEL,
            groq_api_key=require_groq_api_key(),
            temperature=0,
            timeout=45,
            max_retries=0,
        )

    if provider == "claude":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model or settings.ANTHROPIC_CHAT_MODEL,
            anthropic_api_key=require_anthropic_api_key(),
            temperature=0,
            timeout=45,
            max_retries=0,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model or settings.OLLAMA_CHAT_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0,
        )

    raise AIProviderConfigError(
        f"Unsupported LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
        "Use 'gemini', 'groq', 'claude', or 'ollama'."
    )


def _model_for_provider(provider: str) -> str:
    return {
        "gemini": settings.GEMINI_CHAT_MODEL,
        "groq": settings.GROQ_CHAT_MODEL,
        "claude": settings.ANTHROPIC_CHAT_MODEL,
        "ollama": settings.OLLAMA_CHAT_MODEL,
    }[provider]


def _configured_provider(provider: str) -> bool:
    if provider == "gemini":
        return bool((settings.GEMINI_API_KEY or "").strip())
    if provider == "groq":
        return bool((settings.GROQ_API_KEY or "").strip())
    if provider == "claude":
        return bool((settings.ANTHROPIC_API_KEY or "").strip())
    if provider == "ollama":
        return True
    return False


def _provider_candidates() -> list[tuple[str, str]]:
    """Build an ordered, de-duplicated list of production AI candidates."""
    primary = normalize_provider(settings.LLM_PROVIDER)
    candidates: list[tuple[str, str]] = []

    if primary == "gemini":
        models = [settings.GEMINI_CHAT_MODEL, *_csv(settings.GEMINI_FALLBACK_MODELS)]
        for model in models:
            if model and (primary, model) not in candidates:
                candidates.append((primary, model))
    else:
        candidates.append((primary, _model_for_provider(primary)))

    for provider in _csv(settings.LLM_FALLBACK_PROVIDERS):
        provider = normalize_provider(provider)
        if provider == primary or not _configured_provider(provider):
            continue
        candidate = (provider, _model_for_provider(provider))
        if candidate not in candidates:
            candidates.append(candidate)

    return candidates


def _invoke_with_resilience(messages) -> tuple[Any, str, str, float]:
    """
    Generate an answer with bounded retry + model/provider failover.

    A transient Gemini 503/429 no longer immediately becomes a user-visible
    RAG failure. The primary model gets a short retry, then Gemini fallback
    models are tried, followed by configured secondary providers.
    """
    last_error: Exception | None = None
    max_attempts = max(1, min(int(settings.AI_MAX_ATTEMPTS), 3))
    base_delay = max(0.25, min(float(settings.AI_RETRY_BASE_SECONDS), 5.0))

    for provider, model in _provider_candidates():
        for attempt in range(1, max_attempts + 1):
            started_at = time.perf_counter()
            try:
                llm = _get_llm(provider=provider, model=model)
                response = llm.invoke(messages)
                latency_ms = (time.perf_counter() - started_at) * 1000

                if provider != normalize_provider(settings.LLM_PROVIDER) or model != settings.GEMINI_CHAT_MODEL:
                    print(
                        f"JANGO AI failover succeeded: provider={provider}, "
                        f"model={model}, attempt={attempt}"
                    )

                return response, provider, model, latency_ms

            except Exception as exc:
                latency_ms = (time.perf_counter() - started_at) * 1000
                last_error = exc

                transient = _is_transient_ai_error(exc)
                print(
                    f"JANGO AI attempt failed: provider={provider}, model={model}, "
                    f"attempt={attempt}/{max_attempts}, transient={transient}, "
                    f"latency_ms={latency_ms:.0f}, error={exc}"
                )

                if not transient:
                    break

                if attempt < max_attempts:
                    time.sleep(base_delay * (2 ** (attempt - 1)))

    if last_error is None:
        raise RuntimeError("No configured AI provider is available")

    raise last_error


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()

    return str(content).strip()


def query_rag(
    rag_request: RagRequest,
    user_id: int,
    db: Session | None = None,
) -> RagResponse:
    question = rag_request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    top_k = max(1, min(rag_request.top_k or 5, 20))

    try:
        results = similarity_search(
            query=question,
            user_id=user_id,
            k=top_k,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document retrieval failed: {exc}",
        ) from exc

    if not results:
        return RagResponse(
            answer="I don't know based on the uploaded documents.",
            sources=[],
            usage=None,
        )

    context_parts = []
    sources = []

    for document, score in results:
        metadata = document.metadata or {}
        document_id = metadata.get("document_id")
        filename = metadata.get("filename", "Unknown")
        page_number = metadata.get("page_number", "Unknown")

        context_parts.append(
            f"\nDocument: {filename}\n"
            f"Page: {page_number}\n\n"
            f"Content:\n{document.page_content}\n"
        )

        sources.append(
            {
                "id": document_id,
                "filename": filename,
                "page_number": page_number,
                "content": document.page_content,
                "score": float(score),
            }
        )

    context = "\n\n---\n\n".join(context_parts)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are an enterprise document assistant.

Answer the user's question ONLY using the supplied document context.

Rules:
- Do not invent facts.
- If the answer is not present in the context, say you don't know.
- Use only information supported by the context.
- Mention the relevant document filename and page when appropriate.
- Keep the answer clear and concise.

Document context:
{context}
""",
            ),
            ("human", "{question}"),
        ]
    )

    messages = prompt.invoke(
        {
            "context": context,
            "question": question,
        }
    )

    primary_provider = normalize_provider(settings.LLM_PROVIDER)
    primary_model = _model_for_provider(primary_provider)

    try:
        response, provider, model, latency_ms = _invoke_with_resilience(messages)
        answer = _content_to_text(response.content)

        if not answer:
            raise RuntimeError("AI provider returned an empty response")

        usage = extract_token_usage(
            response,
            prompt_text=f"{context}\n{question}",
            output_text=answer,
        )

        if db is not None:
            record_usage(
                db,
                user_id=user_id,
                provider=provider,
                model=model,
                operation="rag_query",
                usage=usage,
                latency_ms=latency_ms,
                status="success",
            )

        return RagResponse(
            answer=answer,
            sources=sources,
            usage={
                **usage,
                "latency_ms": round(latency_ms, 2),
                "provider": provider,
                "model": model,
                "estimated_cost_usd": calculate_cost_usd(
                    int(usage["input_tokens"]),
                    int(usage["output_tokens"]),
                ),
            },
        )

    except Exception as exc:
        if db is not None:
            try:
                failed_usage = extract_token_usage(
                    None,
                    prompt_text=f"{context}\n{question}",
                )
                record_usage(
                    db,
                    user_id=user_id,
                    provider=primary_provider,
                    model=primary_model,
                    operation="rag_query",
                    usage=failed_usage,
                    latency_ms=0,
                    status="error",
                )
            except Exception:
                db.rollback()

        # Do not expose provider internals to end users after all failovers
        # have been exhausted. Render logs contain the detailed root cause.
        raise HTTPException(
            status_code=503,
            detail=(
                "JANGO could not generate an answer right now. "
                "The AI provider is temporarily unavailable. "
                "Please try again in a few seconds."
            ),
        ) from exc
