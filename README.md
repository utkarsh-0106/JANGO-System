# JANGO --- Enterprise Document Intelligence Platform

JANGO is an AI-powered document intelligence platform for uploading,
indexing, searching, and asking natural-language questions about
documents and structured data. It combines a React/Vite frontend,
FastAPI backend, relational metadata storage, ChromaDB vector search,
configurable AI providers, and Telegram integration.

**Repository:** https://github.com/utkarsh-0106/JANGO-System

------------------------------------------------------------------------

## Table of Contents

-   [Overview](#overview)
-   [Features](#features)
-   [Architecture](#architecture)
-   [Core Workflows](#core-workflows)
-   [Technology Stack](#technology-stack)
-   [Project Structure](#project-structure)
-   [Local Development](#local-development)
-   [Environment Configuration](#environment-configuration)
-   [Telegram Integration](#telegram-integration)
-   [Testing](#testing)
-   [Deployment](#deployment)
-   [Security and Production
    Considerations](#security-and-production-considerations)
-   [Known Limitations](#known-limitations)
-   [Documentation](#documentation)
-   [Author](#author)

## Overview

JANGO allows authenticated users to upload supported files, extract and
index their contents, and ask questions grounded in retrieved document
passages. The ingestion pipeline extracts text, creates chunks and
embeddings, and stores vectors in ChromaDB. At query time, the RAG
service retrieves relevant passages and supplies them as context to a
configured language model.

The relational database stores users, document metadata, and processing
state. The vector database stores embeddings and retrieval metadata.
Configurable AI providers support hosted inference and local inference
where the required services and models are available.

JANGO also integrates with Telegram. Users can link a Telegram account,
ask document-related questions through the bot, and use supported
document delivery workflows.

## Features

### Document ingestion and management

-   Multi-format document upload and validation.
-   Background ingestion for supported document formats.
-   Text extraction, chunking, embedding generation, and ChromaDB
    indexing.
-   Per-user document ownership and retrieval scoping.
-   SHA-256 content hashing for duplicate-content detection.
-   Idempotency-key handling for repeated upload requests.
-   Processing state, timestamps, error details, and ingestion-attempt
    tracking.
-   Retry endpoint for supported failed document-processing jobs.
-   Source metadata where available, such as PDF page, slide, sheet,
    row, or section.

### Retrieval-Augmented Generation

-   Document question answering using retrieved passages as context.
-   Vector retrieval through ChromaDB.
-   Hybrid lexical and semantic retrieval where enabled by the
    configured implementation.
-   Retrieval evaluation metrics and evaluation fixtures.
-   User-scoped retrieval to help prevent cross-user document access.
-   Source/document information returned where available.

### Accounts and persistence

-   JWT-based authentication.
-   Password hashing.
-   FastAPI request validation and API orchestration.
-   SQLAlchemy relational persistence.
-   Database initialization and schema migration support.
-   SQLite for local development; production database depends on
    deployment configuration.

### AI provider configuration

-   Configurable language-model and embedding providers.
-   Provider and model selection through environment configuration.
-   Support for local inference through Ollama when the required models
    are installed.
-   AI-generated answers, summaries, and supported report workflows.
-   Provider configuration and failure handling depend on the active
    implementation and environment.

### Telegram integration

-   Telegram bot integration.
-   Account linking using a one-time link code.
-   Authenticated API endpoints for Telegram status and supported
    delivery actions.
-   HTTPS webhook endpoint for incoming bot updates.
-   Document-related Q&A through the configured backend RAG/AI workflow.
-   Supported document delivery and AI-generated content workflows.
-   Webhook request verification using a configured Telegram webhook
    secret.

### Reliability, testing, and deployment

-   Idempotent upload handling and content-based duplicate detection.
-   Document processing lifecycle tracking and failure diagnostics.
-   Automated backend tests using pytest.
-   Frontend production build using Vite.
-   Environment-based configuration.
-   Deployment configuration for a Vercel frontend and Render backend.
-   Architecture, deployment, environment, troubleshooting, and
    upgrade-audit documentation.

> Runtime capabilities depend on the checked-out code, configured
> environment variables, AI provider, database, storage configuration,
> and deployment environment.

## Architecture

``` mermaid
flowchart TD
    USER[User] --> WEB[React + Vite Frontend]
    USER --> TGUSER[Telegram User]

    WEB -->|REST / JSON| API[FastAPI Backend]
    TGUSER <--> BOT[Telegram Bot API]
    BOT -->|HTTPS Webhook| TGH[Telegram Webhook Router]
    TGH --> API

    API --> AUTH[Authentication and Authorization]
    API --> DOCS[Document Router]
    API --> RAG[RAG and Retrieval Services]
    API --> TGS[Telegram Service]

    AUTH --> SQL[(Relational Database)]
    DOCS --> SQL
    TGS --> SQL

    DOCS --> INGEST[Background Ingestion]
    INGEST --> EXTRACT[Text Extraction]
    EXTRACT --> CHUNK[Text Chunking]
    CHUNK --> EMBED[Embedding Provider]
    EMBED --> VS[Vector Store Service]
    VS --> CHROMA[(ChromaDB)]

    RAG --> RETRIEVE[Hybrid / Semantic Retrieval]
    RETRIEVE --> CHROMA
    RETRIEVE --> CONTEXT[Build Prompt Context]
    CONTEXT --> LLM[Configured Language Model]
    LLM --> ANSWER[Answer and Available Sources]

    ANSWER --> API
    API --> WEB
    TGS -->|Messages and supported files| BOT
    BOT --> TGUSER
```

### Component responsibilities

  -----------------------------------------------------------------------
  Component                           Responsibility
  ----------------------------------- -----------------------------------
  React + Vite                        Web interface for authentication,
                                      documents, chat, and Telegram
                                      controls

  FastAPI                             API routing, request validation,
                                      and service orchestration

  Authentication                      User identity and protected
                                      endpoint access

  SQLAlchemy                          Relational data access

  Relational database                 Users, document metadata, and
                                      processing state

  Ingestion service                   Text extraction, chunking, and
                                      indexing workflow

  Embedding provider                  Converts text into vector
                                      representations

  ChromaDB                            Vector storage and similarity
                                      retrieval

  RAG service                         Retrieves relevant chunks and
                                      coordinates answer generation

  Language model                      Generates responses using the
                                      question and retrieved context

  Telegram router/service             Account linking, webhook
                                      processing, and supported bot
                                      operations
  -----------------------------------------------------------------------

## Core Workflows

### 1. Document ingestion

1.  An authenticated user uploads a supported file.
2.  FastAPI validates the request and checks the relevant access rules.
3.  The backend applies request idempotency and content-deduplication
    checks where configured.
4.  A document record is created or an existing result is reused as
    appropriate.
5.  The ingestion service extracts text and divides it into chunks.
6.  The configured embedding provider generates vector representations.
7.  The vector-store service indexes chunks and metadata in ChromaDB.
8.  The document processing state is updated with the outcome and
    relevant timestamps.

The configured chunking strategy and limits are defined by the active
implementation and settings.

### 2. Document question answering

1.  The user asks a question through the web interface or linked
    Telegram account.
2.  The backend identifies the user and scopes access to that user's
    documents.
3.  The RAG service retrieves relevant passages.
4.  Retrieved passages are assembled into context.
5.  The configured language model generates an answer.
6.  The response and available source information are returned through
    the originating channel.

### 3. Duplicate upload prevention

JANGO uses two complementary mechanisms where configured:

-   **Request idempotency:** identifies a logical upload request so a
    repeated request can reuse an earlier result.
-   **Content deduplication:** uses SHA-256 content hashes to detect
    identical file contents, including files with different names.

These mechanisms reduce duplicate work but do not, by themselves,
guarantee atomic writes across the relational database, filesystem, and
vector store.

### 4. Telegram account linking and webhook

1.  The authenticated web application requests a link code.
2.  The user submits the supported command and code to the JANGO bot.
3.  The backend validates the code and associates the Telegram account
    with the JANGO user.
4.  Telegram sends bot updates to the configured HTTPS webhook.
5.  The backend verifies the configured webhook secret and delegates
    supported operations to the Telegram service.
6.  Supported questions use the backend's document/RAG workflow;
    supported delivery actions use the Telegram Bot API.

Check the current Telegram router and Telegram documentation for the
exact webhook path and supported commands.

## Technology Stack

  -----------------------------------------------------------------------
  Layer                               Technologies
  ----------------------------------- -----------------------------------
  Frontend                            React, JavaScript, Vite, CSS

  Backend                             Python, FastAPI, Pydantic

  API                                 REST/JSON, Telegram webhooks

  Database access                     SQLAlchemy

  Relational database                 SQLite locally; configured
                                      production database

  Authentication                      JWT, password hashing

  Document processing                 Format-aware extraction, chunking,
                                      background ingestion

  Vector database                     ChromaDB

  Retrieval                           Semantic and hybrid retrieval
                                      components

  AI                                  Configurable embedding and
                                      language-model providers

  Telegram                            Telegram Bot API

  Testing                             pytest

  Frontend build                      Vite

  Deployment configuration            Vercel, Render
  -----------------------------------------------------------------------

## Project Structure

``` text
JANGO-System/
├── alembic/
│   ├── env.py
│   └── versions/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── evaluation/
│   │   ├── db.py
│   │   └── settings.py
│   ├── tests/
│   └── .env.example
├── frontend/
│   └── src/
│       ├── components/
│       └── pages/
├── docs/
│   └── UPGRADE_AUDIT.md
├── tests/
│   └── test_settings_security.py
├── ARCHITECTURE.md
├── DEPLOYMENT.md
├── ENVIRONMENT_VARIABLES.md
├── TROUBLESHOOTING.md
├── render.yaml
├── requirements.txt
└── README.md
```

This is a representative structure. Consult the repository for all
modules and paths.

## Local Development

### Prerequisites

-   Git
-   Python version supported by the repository's runtime/dependency
    configuration
-   Node.js and npm
-   A configured relational database
-   A configured embedding provider and language-model provider
-   Ollama and required models if using local inference
-   Telegram bot token only if testing Telegram integration

### 1. Clone the repository

``` bash
git clone https://github.com/utkarsh-0106/JANGO-System.git
cd JANGO-System
```

### 2. Configure and start the backend

From the repository root:

``` bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure the required environment variables. For the current repository
layout, start the backend from the project root with:

``` bash
python -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

If dependencies are maintained in a separate backend requirements file,
follow the dependency configuration used by the deployment setup.

### 3. Start the frontend

Open another terminal:

``` bash
cd frontend
npm install
npm run dev
```

Configure the frontend API base URL to point to the backend address used
in local development. Never place private API keys, Telegram bot tokens,
or webhook secrets in frontend code.

### 4. Run tests

From the repository root, activate the Python environment and run:

``` bash
python -m pytest tests backend/tests -v
```

### 5. Build the frontend

``` bash
cd frontend
npm install
npm run build
```

Test and build results depend on the current checkout, installed
dependencies, environment configuration, and external services.

## Environment Configuration

Use `.env.example` and `backend/.env.example` as references. Put real
values in a local ignored `.env` file or in the deployment provider's
secret/environment settings.

  Variable                        Purpose
  ------------------------------- ----------------------------------------
  `ENVIRONMENT`                   Runtime environment
  `DATABASE_URL`                  Relational database connection
  `SECRET_KEY`                    Authentication/signing secret
  `ALGORITHM`                     JWT signing algorithm
  `ACCESS_TOKEN_EXPIRE_MINUTES`   Token lifetime
  `CORS_ORIGINS`                  Allowed frontend origins
  `LLM_PROVIDER`                  Selected language-model provider
  `EMBEDDING_PROVIDER`            Selected embedding provider
  `GEMINI_API_KEY`                Optional Gemini credential
  `GROQ_API_KEY`                  Optional Groq credential
  `ANTHROPIC_API_KEY`             Optional Anthropic credential
  `OLLAMA_BASE_URL`               Ollama server URL
  `OLLAMA_CHAT_MODEL`             Local chat model name
  `OLLAMA_EMBEDDING_MODEL`        Local embedding model name
  `CHROMA_PERSIST_DIRECTORY`      Vector-store persistence directory
  `DOCUMENT_STORAGE_DIRECTORY`    Uploaded-document storage directory
  `TELEGRAM_BOT_TOKEN`            Backend Telegram Bot API token
  `TELEGRAM_WEBHOOK_SECRET`       Secret used to verify webhook requests
  `VITE_API_URL`                  Frontend API base URL

Important:

-   Keep real `.env` files out of version control.
-   Use blank values or clearly fake placeholders in example files.
-   Never put Telegram bot tokens, webhook secrets, database passwords,
    or signing secrets in `VITE_*` variables.
-   Configure backend secrets in the backend hosting environment.
-   Verify variable names against `backend/app/settings.py` and the
    active deployment configuration.

## Telegram Integration

To configure the bot:

1.  Create or select a Telegram bot.
2.  Set `TELEGRAM_BOT_TOKEN` in the backend environment.
3.  Generate a long random webhook secret and set
    `TELEGRAM_WEBHOOK_SECRET`.
4.  Deploy the backend to an HTTPS URL.
5.  Register the Telegram webhook using the exact route and
    secret-header format expected by the implementation.
6.  Verify webhook status and inspect backend logs.
7.  Link a test account and test supported Q&A and delivery workflows.

Do not expose the bot token or webhook secret in frontend code. The
production webhook must target the deployed backend, not a temporary
local tunnel.

## Testing

The upgraded source copy was tested during this project update:

-   **Backend:** 68 tests passed.
-   **Warnings:** 34 warnings were reported.
-   **Frontend:** Vite production build completed successfully.

These are results from the tested source copy at the time of the
upgrade; rerun the commands above against the exact commit and
deployment environment before release.

Before a production release, verify:

-   Frontend production build succeeds.
-   Backend tests pass.
-   Protected endpoints reject unauthenticated requests.
-   Document retrieval and delivery respect user ownership.
-   Invalid Telegram webhook secrets are rejected.
-   AI-provider and Telegram API failures are handled safely.
-   Database, uploaded-file, and vector-store persistence work as
    expected.

## Deployment

JANGO includes deployment configuration for a Vercel frontend and Render
backend. Configuration files do not prove that a deployment is live or
healthy; verify the actual service settings and deployment logs.

### Render backend

Verify:

-   Python runtime and dependency installation.
-   Production `DATABASE_URL`.
-   Strong authentication/signing secrets.
-   CORS origins for the deployed frontend.
-   AI provider credentials and model settings.
-   Telegram bot token and webhook secret, if Telegram is enabled.
-   Persistent storage for uploaded files and ChromaDB, or managed
    alternatives.
-   Health checks, logs, and restart behavior.

**Background processing limitation:** document ingestion currently uses
FastAPI in-process background tasks. Jobs are not durably queued across
process crashes. Interrupted jobs are marked failed at startup and can
be retried through the supported document retry endpoint. For
multi-instance or high-volume production, use a durable worker queue
before scaling beyond a single API instance.

**Storage limitation:** a Render disk can persist document and ChromaDB
files for a single service instance when configured. It is not shared
storage for horizontally scaled instances. Use shared object storage and
an appropriate shared vector-store architecture before scaling out.

### Vercel frontend

-   Configure the frontend project root and build command.
-   Set `VITE_API_URL` to the deployed backend URL.
-   Redeploy after changing environment variables.
-   Do not place backend secrets in client-exposed `VITE_*` variables.

## Security and Production Considerations

-   Use a strong, randomly generated production signing secret.
-   Store API keys, bot tokens, and webhook secrets only in backend
    secret configuration.
-   Enforce authorization on every document access and delivery path.
-   Scope relational queries and vector retrieval to the authenticated
    user's documents.
-   Validate uploaded files and enforce configured upload limits.
-   Avoid logging credentials, passwords, document contents, or
    sensitive user data.
-   Configure restrictive CORS origins and HTTPS endpoints.
-   Review rate limiting, provider timeouts, retry behavior, and error
    logging.
-   Confirm database, uploaded-file, and vector-store persistence before
    relying on production deployments.
-   Test account linking, webhook authentication, and user isolation
    before public release.

Security properties must be verified against the implementation and
tests. This README is not a substitute for a security audit.

## Known Limitations

-   Scanned/image-only PDFs require OCR; OCR is not included in the
    documented ingestion workflow.
-   Legacy binary Word `.doc` and PowerPoint `.ppt` formats are not
    supported.
-   Macro-enabled Office files are not supported.
-   Spreadsheet files are indexed as textual content; formula
    recalculation and exact spreadsheet computation are not provided.
-   Image understanding is not part of the documented document-ingestion
    workflow.
-   In-process background tasks are not durable across process crashes.
-   Local SQLite, uploaded files, and local ChromaDB data do not
    automatically migrate to a hosted environment.
-   A single-instance persistent disk is not shared storage for multiple
    backend instances.
-   Database, filesystem, and vector-store writes are not guaranteed to
    be one atomic transaction.

Confirm the exact accepted extensions, file-size limits, and provider
behavior against the current code and environment configuration.

## Documentation

-   [Architecture](ARCHITECTURE.md)
-   [Deployment Guide](DEPLOYMENT.md)
-   [Environment Variables](ENVIRONMENT_VARIABLES.md)
-   [Troubleshooting](TROUBLESHOOTING.md)
-   [Upgrade Audit](docs/UPGRADE_AUDIT.md)

## Author

**Utkarsh Maheshwari**

-   GitHub: https://github.com/utkarsh-0106
-   Repository: https://github.com/utkarsh-0106/JANGO-System

------------------------------------------------------------------------

**JANGO --- Enterprise Document Intelligence Platform**


## Workspace Settings

Authenticated users can open **Settings** from the sidebar to manage their personal JANGO preferences.

- Save a default response language (Automatic, English, Hindi, or Hinglish).
- Save the retrieval Top-K value (1–20; the UI offers common presets). Ask Jango uses this saved value for subsequent queries.
- View the configured primary AI provider and model. Provider credentials remain server-side and are never returned by the settings API.
- Change the account password after verifying the current password.

Preferences are stored on the user record. Existing databases receive backward-compatible defaulted columns (`auto` and `5`) during application startup; existing user accounts and documents are preserved. The current Gold & Silver appearance remains the fixed workspace theme.
