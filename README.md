# JANGO — Enterprise Document Intelligence Platform

JANGO is an enterprise document intelligence platform that lets users upload documents, process them through a Retrieval-Augmented Generation (RAG) pipeline, and ask questions against their private knowledge base.

## 🎬 Project Demo

[▶️ Watch the 20-second project demo](https://portfolio-dqyw-opal.vercel.app/videos/jango.mp4)

## ✨ Features

- 🔐 JWT-based authentication
- 📄 PDF document upload and processing
- 🧩 Document chunking and embedding
- 🔎 Semantic search with ChromaDB
- 🤖 RAG-based question answering
- 🔒 User-scoped document isolation
- 📚 Source-grounded answers
- ⚡ FastAPI backend
- ⚛️ React frontend
- 🗄️ SQLAlchemy database integration

## 🧠 RAG Pipeline

```text
PDF Upload
    ↓
Text Extraction
    ↓
Document Chunking
    ↓
Embeddings
    ↓
ChromaDB
    ↓
Semantic Search
    ↓
LLM
    ↓
Source-Grounded Answer
🛠️ Tech Stack

Frontend

React
Vite
TypeScript

Backend

Python
FastAPI
Pydantic
SQLAlchemy

AI / RAG

LangChain
ChromaDB
Ollama
Qwen3

Database & Security

SQLite / PostgreSQL
JWT
bcrypt
📌 Project

JANGO is designed around private, user-scoped document intelligence, allowing users to query their uploaded knowledge base while keeping document retrieval isolated between users.

## AI Cost & Token Tracking

JANGO now includes per-user AI observability for RAG generation:

- Input, output, and total token tracking from LangChain provider usage metadata.
- Conservative token estimation when a provider does not expose usage counts.
- Request latency and success/error status.
- Provider/model-level usage aggregation.
- Configurable estimated USD pricing per 1M input/output tokens.
- Local Ollama is represented as $0.00 by default.
- Protected `/api/usage/summary` and `/api/usage/recent` endpoints.
- Premium frontend Analytics page with daily token activity, model usage, pricing, and recent request log.

Configure cloud-provider pricing in `.env` when needed:

```env
AI_INPUT_COST_PER_1M_USD=0
AI_OUTPUT_COST_PER_1M_USD=0
```

These values are estimates only; provider pricing should be configured from the provider's current pricing page.

## Production deployment

JANGO is designed as a Vercel frontend + Render FastAPI backend deployment.

### Cloud AI providers

The backend supports:
- Gemini for LLM and embeddings
- Groq for LLM inference
- Claude/Anthropic for LLM inference
- Ollama for local development

For production RAG, use `EMBEDDING_PROVIDER=gemini`. Groq and Claude are generation providers; Gemini supplies the embedding model.

### Render

The included `render.yaml` provisions a FastAPI web service, a persistent data disk for Chroma/PDFs, and PostgreSQL. Set the API keys and `CORS_ORIGINS` in Render's Environment settings.

### Vercel

Deploy the `frontend` directory as a Vite application and set `VITE_API_URL` to the public Render backend URL.

Never commit real API keys or `.env` files.
