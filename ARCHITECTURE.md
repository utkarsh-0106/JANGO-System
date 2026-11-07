# JANGO architecture (audited source state)

## Runtime components

- **React + Vite** (`frontend/`): SPA, Axios API client, dashboard, chat, document management, Telegram linking.
- **FastAPI** (`backend/app/`): authentication, document APIs, RAG APIs, usage reporting, Telegram webhook and delivery.
- **SQLAlchemy**: users, document metadata, AI usage; PostgreSQL is expected in production and SQLite is supported for local development.
- **ChromaDB**: persisted vector collection; metadata includes `user_id`, `document_id`, filename and source location.
- **Filesystem**: uploaded source documents. Render config mounts `/var/data` for both source files and Chroma persistence.
- **LLM adapters**: Gemini, Groq, Anthropic Claude, Ollama. Embeddings are independently configured (Gemini, Ollama, Chroma default).

## Document lifecycle

Upload validates extension, size, binary signatures for container formats, parses structured formats for validity, computes SHA-256 and stores a user-scoped SQL record. The UI-facing status values remain compatible (`uploaded`, `processing`, `ready`, `failed`); `deleting` is used during deletion. Processing records attempts, timestamps and a sanitized failure reason. Extraction/chunking completes before old vectors are replaced. If vector insertion fails, partial vectors are removed where possible and the row remains retryable. Deletion marks the row first, removes vectors and the source file, then removes SQL metadata.

SQL, Chroma and filesystem operations are not one atomic transaction. Failed compensation can leave orphaned external data; keep the SQL record for reconciliation rather than falsely reporting success.

## AI resilience

The configured LLM primary is attempted first. Gemini model fallbacks are followed by configured secondary providers (`LLM_FALLBACK_PROVIDERS`). Only transient errors are retried; retry count is bounded and backoff includes jitter. Provider logs contain provider/model, attempt, latency and exception class, not raw exception text. Embeddings are a separate provider setting; each chunk records its embedding provider/model, and retrieval filters on both fields as well as user ID. Changing embedding provider/model therefore fails closed rather than comparing incompatible vector spaces. Reprocess all documents with the authenticated `POST /api/documents/{id}/retry` endpoint after a model change.

## Isolation and trust boundaries

Every retrieval query filters on authenticated `user_id`; document routes scope lookups to the current user. Retrieved document text is explicitly untrusted context in the system prompt. Never interpret instructions inside a document as privileged instructions. Keep secrets in environment variables and do not commit `.env` files.

## Current scaling boundary

Ingestion uses FastAPI in-process background tasks, not a durable queue. A process restart can interrupt a task. Startup marks stale `processing` rows as `failed`, and the owner can retry with `POST /api/documents/{id}/retry`. This is appropriate only for modest single-instance use. Before multi-instance/high-volume deployment, move ingestion to Celery/RQ/Arq with Redis or another durable broker, use object storage for source files, and use a vector service with shared multi-instance semantics. Render's attached disk is single-service-instance storage, not a shared filesystem.

## Retrieval and ingestion capabilities not present in this checkout

The active production retrieval path is Chroma semantic similarity search with user and embedding-identity filters. The repository contains offline Recall@K, Precision@K, MRR and NDCG@K metric utilities plus a synthetic fixture; it does not currently implement BM25/hybrid fusion, a cross-encoder reranker, an automated answer-faithfulness benchmark, or a benchmark runner over real production queries. PDF extraction is text-based; OCR for scanned/image-only PDFs is not installed or implemented. These features are not represented as complete in this upgrade.
