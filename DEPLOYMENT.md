# Deployment and local setup

## Local development

Requirements: Python 3.11/3.12 recommended, Node.js 20+ compatible with the Vite version in `frontend/package.json`, and optional Ollama if using local models.

1. Clone/unzip the project and enter the repository root.
2. Create a virtual environment and install backend dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. Edit `.env`: set `SECRET_KEY` to a random local value; keep `DATABASE_URL=sqlite:///./sql_app.db`. For cloud AI set `LLM_PROVIDER=gemini`, `EMBEDDING_PROVIDER=gemini`, and provide `GEMINI_API_KEY`. For Ollama set both providers appropriately and start Ollama with the configured models.
4. Start API from repository root:

   ```bash
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```

   Startup creates missing SQL tables and applies the repository's backward-compatible column additions. Liveness is `GET /api/health`; readiness is `GET /api/ready`.
5. In another terminal:

   ```bash
   cd frontend
   cp .env.example .env
   npm ci
   npm run dev
   ```

   Set `VITE_API_URL=http://localhost:8000` in `frontend/.env`.
6. Run backend tests from repository root with `pytest -q`. Build frontend with `cd frontend && npm run build`.

## Render backend

1. Push the repository to GitHub and create a Render Blueprint from `render.yaml` (or create a Python web service with the same settings).
2. Provision the PostgreSQL database and attach the persistent disk mounted at `/var/data`.
3. Configure `DATABASE_URL` to the Render PostgreSQL connection string; `render.yaml` links the database automatically. Production startup intentionally refuses SQLite.
4. Set `SECRET_KEY` to a strong random value (Render's `generateValue` is configured), `GEMINI_API_KEY` and any desired fallback credentials. Set `CORS_ORIGINS` to the exact Vercel origin, e.g. `https://your-app.vercel.app` (comma-separated if using preview/custom domains).
5. Keep `CHROMA_PERSIST_DIRECTORY=/var/data/chroma` and `DOCUMENT_STORAGE_DIRECTORY=/var/data/documents`. Both directories live on the attached disk.
6. **Database migration preparation:** for a brand-new empty PostgreSQL database, the configured Render start command runs `alembic upgrade head` before Uvicorn. For an existing populated database that has no `alembic_version` table, take a backup, verify that `users`, `documents`, and `ai_usage` match the existing JANGO schema, then run `alembic stamp 20231010_123456` once in Render Shell. The next deploy applies the additive migration. If the database already has an Alembic revision, do not stamp it; inspect the revision and run `alembic upgrade head`.
7. Deploy. Render checks `/api/ready`, which verifies SQL connectivity and storage-directory setup. `/api/health` is liveness only.
8. Verify `/api/ready`, register/login, upload a small supported document, wait for `ready`, query it, and test deletion. Configure Telegram webhook only after the public backend URL and secrets are set.

**Important:** Render's disk is persistent but attached to one service instance. Do not scale this service horizontally while using local filesystem documents and local Chroma persistence. A durable queue and shared object/vector storage are still required for multi-instance operation.

## Vercel frontend

1. Import the `frontend/` directory as the Vercel project root.
2. Framework preset: Vite. Build command: `npm run build`; output directory: `dist`.
3. Add `VITE_API_URL=https://<your-render-service>.onrender.com` (no trailing slash required) to Production and Preview environments as appropriate.
4. Deploy, then add the final Vercel domain to backend `CORS_ORIGINS` in Render and redeploy/restart the backend.
5. Verify login, document upload/status, chat, and Telegram linking from the deployed frontend.

## Database changes

SQLAlchemy model metadata is created on startup for fresh installations; the current startup also performs backward-compatible additive column upgrades for legacy document and Telegram fields. Alembic metadata is wired for autogeneration, but the historical initial migration predates the complete current schema. Before relying on Alembic for an existing production database, baseline/stamp that database after reviewing its schema and create a migration from the actual deployed revision. Back up PostgreSQL before schema changes. Do not blindly run the historical initial migration against an existing populated database.

## Backups

Back up PostgreSQL using Render's supported backup/PITR facilities. Back up `/var/data/documents` and `/var/data/chroma` together and restore them as a consistent set. Chroma data without matching source files/SQL metadata (or vice versa) requires reconciliation. Test restores periodically.
