# Environment variables

Set these in the backend service environment. Never commit real values.

| Variable | Required | Default / example | Purpose |
|---|---:|---|---|
| `ENVIRONMENT` | production | `development` | Runtime mode; production rejects SQLite and placeholder secrets. |
| `DATABASE_URL` | production | `sqlite:///./sql_app.db` locally | SQLAlchemy URL. PostgreSQL `postgres://` and `postgresql://` are normalized to psycopg v3. |
| `SECRET_KEY` | production | generated locally | JWT signing secret; use a long random value. |
| `ALGORITHM` | no | `HS256` | JWT algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime. |
| `CORS_ORIGINS` | production | `http://localhost:5173` | Comma-separated exact frontend origins. |
| `DB_POOL_SIZE` | no | `5` | PostgreSQL SQLAlchemy pool size. |
| `DB_MAX_OVERFLOW` | no | `5` | Maximum overflow connections. |
| `MAX_UPLOAD_SIZE_MB` | no | `10` | Upload cap (1–100 MB). |
| `MAX_PDF_PAGES` | no | `500` | PDF page cap. |
| `MAX_INGESTION_CHUNKS` | no | `20000` | Per-document chunk cap. |
| `LLM_PROVIDER` | yes for AI | `gemini` | `gemini`, `groq`, `claude`, or `ollama`. |
| `LLM_FALLBACK_PROVIDERS` | no | `groq,claude` | Ordered secondary LLM providers. |
| `AI_MAX_ATTEMPTS` | no | `2` | Bounded attempts per candidate. |
| `AI_RETRY_BASE_SECONDS` | no | `1` | Exponential retry base. |
| `AI_REQUEST_TIMEOUT_SECONDS` | no | `45` | Documented timeout setting; provider adapters currently use provider-specific timeout values. |
| `GEMINI_API_KEY` | if Gemini | empty | Gemini credential. |
| `GEMINI_CHAT_MODEL` | no | `gemini-3.8-flash` | Gemini chat model. |
| `GEMINI_FALLBACK_MODELS` | no | `gemini-3.7-flash,gemini-3.6-flash` | Ordered Gemini model fallbacks. |
| `GEMINI_EMBEDDING_MODEL` | if Gemini embeddings | `gemini-embedding-2` | Embedding model; keep fixed for an index. |
| `GROQ_API_KEY` | if Groq | empty | Groq credential. |
| `GROQ_CHAT_MODEL` | no | `openai/gpt-oss-120b` | Groq-hosted model. |
| `ANTHROPIC_API_KEY` | if Claude | empty | Anthropic credential. |
| `ANTHROPIC_CHAT_MODEL` | no | `claude-sonnet-4-5` | Claude model. |
| `OLLAMA_BASE_URL` | if Ollama | `http://localhost:11434` | Ollama server URL. |
| `OLLAMA_CHAT_MODEL` | no | `qwen3:8b` | Ollama chat model. |
| `OLLAMA_EMBEDDING_MODEL` | no | `nomic-embed-text` | Ollama embedding model. |
| `EMBEDDING_PROVIDER` | yes for ingestion/RAG | `gemini` | `gemini`, `ollama`, or `chroma`; independent of LLM provider. |
| `CHROMA_PERSIST_DIRECTORY` | no | `./storage/chroma` | Persistent Chroma path; use Render disk path in production. |
| `DOCUMENT_STORAGE_DIRECTORY` | no | `./storage/documents` | Uploaded source storage; use Render disk path in production. |
| `AI_INPUT_COST_PER_1M_USD` | no | `0` | Configured input cost estimate. |
| `AI_OUTPUT_COST_PER_1M_USD` | no | `0` | Configured output cost estimate. |
| `TELEGRAM_BOT_TOKEN` | optional | empty | Telegram bot token. |
| `TELEGRAM_WEBHOOK_SECRET` | optional | empty | Telegram webhook header secret. |

Frontend (`frontend/.env`):

- `VITE_API_URL`: backend base URL, e.g. `http://localhost:8000` locally or the deployed Render service URL in Vercel.

The checked-in `.env.example` files contain placeholders only. For production, set environment variables in Render/Vercel dashboards; do not upload `.env` files.
