# JANGO — Private AI

> **Enterprise Document Intelligence & RAG Platform**

JANGO is a production-deployed private AI knowledge assistant that allows users to securely upload documents and interact with them using natural-language questions.

Instead of sending documents directly to an LLM, JANGO uses a Retrieval-Augmented Generation (RAG) pipeline to retrieve relevant document context first and then generate grounded answers with source references.


### Multiple PDF Upload
Select and upload multiple PDF files from the dashboard in one selection. Files are validated individually (PDF only, maximum 10 MB each) and uploaded sequentially through the existing authenticated upload endpoint; ingestion runs independently in the background. The dashboard reports successful and failed uploads separately.

## 🚀 Live Demo

**Live Application:**  
https://jango-system.vercel.app

**Backend API:**  
https://jango-system.onrender.com

**API Documentation:**  
https://jango-system.onrender.com/docs

---

## ✨ Features

### 🔐 Authentication & Security
- JWT-based authentication
- Secure password hashing
- Protected API routes
- User-specific document isolation
- Users can only retrieve their own documents

### 📄 Document Intelligence
- Upload PDF documents
- Automatic PDF text extraction
- Page-aware document processing
- Intelligent text chunking
- Document processing status tracking
- Re-processing support
- Document deletion with vector cleanup

### 🧠 RAG Pipeline

JANGO uses a complete Retrieval-Augmented Generation architecture:

```text
PDF Upload
    ↓
PDF Text Extraction
    ↓
Text Chunking
    ↓
Embeddings
    ↓
Chroma Vector Database
    ↓
Hybrid Retrieval
    ├── Semantic Vector Search
    └── BM25 Keyword Search
    ↓
Reciprocal Rank Fusion
    ↓
Relevant Context
    ↓
Gemini LLM
    ↓
Grounded Answer + Sources
```

### 🔎 Hybrid Search

JANGO combines:

- Semantic vector retrieval
- BM25 keyword retrieval
- Reciprocal Rank Fusion (RRF)

This improves retrieval for both conceptual questions and exact technical terms.

### 🤖 AI Resilience

The production RAG pipeline includes:

- Automatic retry for transient AI failures
- Exponential backoff
- Gemini model fallback
- Provider fallback support
- Graceful handling of temporary AI availability problems

### 💰 AI Usage & Cost Tracking

JANGO tracks AI usage including:

- AI request count
- Input tokens
- Output tokens
- Total tokens
- Estimated cost
- Average latency
- Model/provider usage
- Recent AI request history

### 📚 Source-Grounded Answers

Every RAG response can display the document sources used to generate the answer.

---

## 🏗️ System Architecture

```text
                         ┌──────────────────────┐
                         │        User          │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ React + Vite         │
                         │ Vercel               │
                         └──────────┬───────────┘
                                    │ HTTPS
                                    ▼
                         ┌──────────────────────┐
                         │ FastAPI Backend      │
                         │ Render               │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
             ┌────────────┐  ┌─────────────┐  ┌────────────┐
             │ PostgreSQL │  │   Chroma    │  │ Gemini AI  │
             │ / Database │  │ Vector DB   │  │    LLM     │
             └────────────┘  └──────┬──────┘  └────────────┘
                                    │
                                    ▼
                              Hybrid Search
                           ┌────────┴────────┐
                           │                 │
                        Vector             BM25
                        Search            Search
                           │                 │
                           └────────┬────────┘
                                    │
                                    ▼
                              RRF Fusion
                                    │
                                    ▼
                              RAG Context
                                    │
                                    ▼
                              Gemini Answer
```

---

## 🛠️ Tech Stack

### Frontend
- React
- Vite
- JavaScript
- Axios
- React Router
- CSS
- Responsive UI

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- JWT Authentication
- bcrypt
- PyPDF
- LangChain

### AI / RAG
- Google Gemini
- ChromaDB
- Embeddings
- BM25
- Hybrid Search
- Reciprocal Rank Fusion (RRF)

### Database & Storage
- PostgreSQL / SQLite depending on environment
- ChromaDB
- File-based document storage

### Deployment
- Vercel — Frontend
- Render — Backend
- GitHub — Source Control

---

## 📊 AI Analytics

JANGO includes an AI analytics dashboard that tracks:

| Metric | Description |
|---|---|
| AI Requests | Number of AI generation requests |
| Input Tokens | Tokens sent to the model |
| Output Tokens | Tokens generated by the model |
| Total Tokens | Combined token usage |
| Estimated Cost | Estimated AI API cost |
| Average Latency | Average model response time |
| Model Usage | Usage grouped by AI model |

---

## 🔄 RAG Request Flow

```text
User Question
      ↓
Authentication Check
      ↓
User Document Scope
      ↓
Hybrid Retrieval
      ↓
Relevant Chunks
      ↓
Context Construction
      ↓
Gemini Generation
      ↓
Response Validation
      ↓
Answer + Sources
```

---

## 🔒 Privacy & Document Isolation

JANGO is designed around private document knowledge bases.

Each document and vector chunk is associated with a user.

Retrieval is filtered by the authenticated user's identity so one user cannot retrieve another user's documents.

```text
User A
 ├── Document A1
 ├── Document A2
 └── Vector Chunks A

User B
 ├── Document B1
 └── Vector Chunks B
```

Queries from User A cannot retrieve User B's document chunks.

---

## 🔎 Retrieval Evaluation Utilities

JANGO includes dependency-free offline retrieval metrics in `backend/app/evaluation/retrieval_metrics.py`:

- Recall@K: fraction of known relevant chunks retrieved in the top K results.
- MRR: rewards finding the first relevant result near the top.
- NDCG@K: evaluates ranking quality with binary relevance labels.

See [`docs/RAG_EVALUATION.md`](docs/RAG_EVALUATION.md) for examples and guidance on creating a reviewed benchmark dataset. These metrics calculate retrieval quality; they do not, by themselves, measure answer faithfulness or prove an improvement.

## 📈 Request Observability

HTTP requests now receive an `X-Request-ID` response header and emit a structured log entry with request ID, method, path, status code, and duration. The middleware deliberately avoids logging request bodies or query parameters. Use the request ID when correlating a browser report with backend logs.

## ⚙️ Continuous Integration

GitHub Actions runs backend tests and frontend lint/build checks on pushes and pull requests to `main`. The workflow is defined in `.github/workflows/ci.yml`.

## 🧪 Testing

The backend includes automated tests covering:

- Authentication
- Document handling
- RAG behavior
- Retrieval
- Hybrid search
- AI provider behavior

Run the backend tests with:

```bash
pytest -q
```

---

## 💻 Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start FastAPI:

```bash
cd ..
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 🌐 Production Deployment

JANGO uses a separated frontend/backend deployment architecture:

```text
GitHub
  │
  ├── Vercel
  │     └── React Frontend
  │
  └── Render
        └── FastAPI Backend
              │
              └── Gemini AI
```

Environment variables are used for production configuration and API credentials.

Secrets such as API keys are never committed to the repository.

---

## 🎯 Why JANGO?

Traditional document search often relies only on keyword matching.

JANGO combines:

```text
Keyword Search
      +
Semantic Search
      +
RRF Ranking
      +
LLM Generation
      =
Grounded AI Answers
```

The goal is to make document interaction feel like talking to a private AI assistant while maintaining document-level access control and source transparency.

---

## 📌 Example Questions

After uploading a resume, technical document, or company knowledge base, users can ask:

```text
What programming languages are mentioned?

What projects are described in this document?

What technologies were used in the backend?

Summarize this document.

What databases are mentioned?

Explain the architecture described in this document.

What information is not available in the document?
```

---

## 🔮 Future Improvements

Potential future improvements include:

- Streaming AI responses
- More AI provider integrations
- Advanced document formats
- OCR for scanned PDFs
- Document collections/workspaces
- Conversation history
- Advanced observability
- Rate limiting
- Enterprise SSO
- Cloud object storage
- More advanced reranking models

---

## 👨‍💻 Author

**Utkarsh Maheshwari**

B.Tech — Computer Science & Engineering

Interested in:

- AI Engineering
- Backend Engineering
- Full-Stack Development
- RAG Systems
- LLM Applications
- System Design

---

## ⭐ Live Project

If you find JANGO interesting, try the live application:

**https://jango-system.vercel.app**

## Duplicate upload protection

The dashboard prevents duplicate upload handlers from running while a batch is in progress. Each file operation sends an `Idempotency-Key` header. The API returns the existing document when the same authenticated user repeats a request with the same key, and a unique database index on `(user_id, idempotency_key)` protects against concurrent duplicate requests. The key is nullable to preserve compatibility with older document records and clients that do not send it. Re-uploading the same PDF as a new operation intentionally creates a new document unless the same idempotency key is reused.


## Duplicate PDF uploads

Uploads are deduplicated per user by SHA-256 of the exact PDF bytes. Uploading the same file under a different filename or idempotency key returns the existing document. Different users may upload the same file independently. Existing database records are preserved during migration; legacy duplicate rows are not automatically deleted.
