# JANGO v2.0 upgrade audit

Audit date: 2026-11-07. Scope: uploaded `JANGO-System(5).zip` source tree. This is a source-code audit; no production credentials or deployed environment were available.

## Checklist and implementation

- [x] Inspected backend, frontend, models, routers, services, tests, deployment files and existing docs.
- [x] Added bounded SQLAlchemy connection pools, pre-ping, SQLite foreign-key/busy-timeout pragmas, and PostgreSQL psycopg URL normalization.
- [x] Refuse production SQLite configuration; reject placeholder/short production JWT secrets and wildcard/empty production CORS.
- [x] Added configurable upload/page/chunk limits and bounded upload reads; added binary magic-byte checks for PDF/Office container formats.
- [x] Added document processing error/timestamp/attempt metadata and backward-compatible startup column upgrades.
- [x] Added retry endpoint and dashboard retry action; dashboard polls for background ingestion status.
- [x] Added compensating vector cleanup on ingestion failure; deletion persists `deleting` state and removes vectors/file before SQL row removal.
- [x] Added startup recovery for stale `processing` rows.
- [x] Added embedding provider/model identity to chunk metadata and retrieval filters to prevent cross-space vector comparisons.
- [x] Added provider retry jitter and structured safe provider logs; use configurable timeout for supported remote LLM adapters.
- [x] Hardened RAG prompt against treating document content as instructions; retrieval errors no longer expose raw backend exception strings.
- [x] Added liveness/readiness endpoints, request IDs, and structured operational logs.
- [x] Wired Alembic metadata and supplied a complete fresh-install baseline plus additive ingestion metadata migration.
- [x] Added Precision@K and a synthetic retrieval evaluation fixture.
- [x] Added architecture, deployment, environment-variable and troubleshooting documentation.

## Findings and limitations retained explicitly

- Document ingestion still uses FastAPI in-process background tasks. It is not durable across process crashes and is not suitable for horizontal scaling. Startup marks stale jobs failed; user retry is available. Redis-backed workers remain a production scale requirement.
- Render's persistent disk and local Chroma/filesystem storage are single-instance. Multi-instance operation requires shared object storage and an appropriate shared vector backend.
- OCR for scanned/image-only PDFs is not implemented; text-based PDF extraction only.
- Active retrieval remains semantic Chroma similarity. BM25/hybrid fusion and cross-encoder reranking are not implemented in the active RAG path.
- Retrieval metrics are utilities with synthetic fixtures; answer faithfulness/citation accuracy are not automatically benchmarked.
- API-wide distributed rate limiting, request quotas, and abuse controls are not implemented.
- Full object-storage abstraction, distributed deletion/reconciliation worker, and durable job retry/dead-letter queue are not implemented.
- The historical initial migration was incomplete; the baseline has been corrected for fresh databases and an additive migration added. Existing populated databases must be backed up and stamped against the legacy baseline before applying the additive migration; see `DEPLOYMENT.md`.
- No live Gemini/Groq/Anthropic/Ollama, Telegram, Render, PostgreSQL or Vercel integration test was possible in this sandbox.

## Verification performed

- Python `compileall` across backend, root entrypoint and tests: passed.
- Dependency-light verification suite (retrieval metrics + production settings validation): 9 passed.
- Full pytest collection was attempted before dependency installation. Collection was blocked because this environment lacks installed `bcrypt` and `langchain_core` (among the project requirements); network access prevented pip installation.
- Frontend dependency installation/build was attempted; `npm ci` timed out because package registry access was unavailable and `npm run build` could not find Vite. No successful frontend build is claimed.
- Archive contents were checked for real `.env`, local database files and common API-key/token patterns; none were found in the extracted source tree.
