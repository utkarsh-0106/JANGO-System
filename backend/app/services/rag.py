from fastapi import HTTPException
from sqlalchemy.orm import Session
import time
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
from backend.app.services.ai_usage import calculate_cost_usd, extract_token_usage, record_usage
from backend.app.settings import settings


def _get_llm():
    provider = normalize_provider(settings.LLM_PROVIDER)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_CHAT_MODEL,
            google_api_key=require_gemini_api_key(),
            temperature=0,
            timeout=60,
            max_retries=2,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.GROQ_CHAT_MODEL,
            groq_api_key=require_groq_api_key(),
            temperature=0,
            timeout=60,
            max_retries=2,
        )

    if provider == "claude":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.ANTHROPIC_CHAT_MODEL,
            anthropic_api_key=require_anthropic_api_key(),
            temperature=0,
            timeout=60,
            max_retries=2,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.OLLAMA_CHAT_MODEL,
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


def query_rag(rag_request: RagRequest, user_id: int, db: Session | None = None) -> RagResponse:
    question = rag_request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    top_k = max(1, min(rag_request.top_k or 5, 20))

    try:
        results = similarity_search(query=question, user_id=user_id, k=top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document retrieval failed: {exc}") from exc

    if not results:
        return RagResponse(answer="I don't know based on the uploaded documents.", sources=[], usage=None)

    context_parts = []
    sources = []
    for document, score in results:
        metadata = document.metadata or {}
        document_id = metadata.get("document_id")
        filename = metadata.get("filename", "Unknown")
        page_number = metadata.get("page_number", "Unknown")
        context_parts.append(
            f"\nDocument: {filename}\nPage: {page_number}\n\nContent:\n{document.page_content}\n"
        )
        sources.append({
            "id": document_id,
            "filename": filename,
            "page_number": page_number,
            "content": document.page_content,
            "score": float(score),
        })

    context = "\n\n---\n\n".join(context_parts)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
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
"""),
        ("human", "{question}"),
    ])

    provider = normalize_provider(settings.LLM_PROVIDER)
    model = _model_for_provider(provider)

    try:
        llm = _get_llm()
        messages = prompt.invoke({"context": context, "question": question})
        started_at = time.perf_counter()
        response = llm.invoke(messages)
        latency_ms = (time.perf_counter() - started_at) * 1000

        content = response.content
        if isinstance(content, str):
            answer = content.strip()
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("text"):
                    parts.append(str(block["text"]))
                elif isinstance(block, str):
                    parts.append(block)
            answer = "\n".join(parts).strip()
        else:
            answer = str(content).strip()

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
                    int(usage["input_tokens"]), int(usage["output_tokens"])
                ),
            },
        )

    except Exception as exc:
        if db is not None:
            try:
                failed_usage = extract_token_usage(None, prompt_text=f"{context}\n{question}")
                record_usage(
                    db,
                    user_id=user_id,
                    provider=provider,
                    model=model,
                    operation="rag_query",
                    usage=failed_usage,
                    latency_ms=0,
                    status="error",
                )
            except Exception:
                db.rollback()
        raise HTTPException(status_code=500, detail=f"RAG generation failed: {exc}") from exc
