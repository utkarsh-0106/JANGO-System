# Troubleshooting

- **`DATABASE_URL must point to PostgreSQL`**: production has no SQLite fallback. Attach/configure the Render PostgreSQL URL.
- **`/api/ready` returns 503**: check Render PostgreSQL connectivity, mounted disk permissions, and configured storage paths. Use `/api/health` to distinguish process liveness.
- **Document remains `failed`**: inspect Render logs by `document_id`; the API stores a sanitized failure reason in document metadata. Retry with `POST /api/documents/{id}/retry` while authenticated.
- **Document shows `processing` after restart**: startup recovery marks stale processing records failed after 15 minutes. Retry from the UI/API.
- **RAG returns no sources**: confirm the document is `ready`, current user owns it, Chroma persistence path is retained, and embedding provider/model has not changed since indexing.
- **Embedding provider/model changed**: do not compare new query vectors with old vectors. Reprocess each document with the authenticated `POST /api/documents/{id}/retry` endpoint. Until reprocessed, old chunks are excluded from retrieval by the embedding identity filter.
- **AI provider unavailable**: verify provider credential, model access, provider priority, and rate limits. Missing fallback credentials are skipped; permanent authentication/configuration errors are not pointlessly retried.
- **Telegram webhook rejected**: verify `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, Telegram's `secret_token` header, and the registered HTTPS webhook URL. Never put bot tokens in logs or support tickets.
- **CORS error**: set `CORS_ORIGINS` to the exact frontend origin (scheme + host; no path), comma-separated for multiple origins.
- **Local Ollama errors**: ensure Ollama is running and the selected chat/embedding models are pulled. Render cannot access a developer machine's localhost Ollama service.
- **Storage loss after redeploy**: verify both directories are under `/var/data` and the Render persistent disk is attached. Do not use local ephemeral paths for production documents or vectors.
- **Horizontal scaling**: current in-process ingestion and local disk/Chroma are single-instance. Add a durable broker/worker, shared object storage and a multi-instance vector backend before scaling.
- **Scanned PDF returns no text**: OCR is not included in this version; upload a text-based PDF or OCR it before upload. Do not expect image-only pages to be indexed.
- **Need keyword/hybrid ranking or reranking**: current active retrieval is semantic Chroma similarity. Offline retrieval metric functions and a synthetic fixture are present, but BM25 fusion and cross-encoder reranking are not yet wired into production retrieval.
