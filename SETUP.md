# Setup

Everything needed to get Prometheus running locally for development/testing:
backend (FastAPI + CLI), background processing (Celery + Redis), and the
React frontend.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (dependency management/venv)
- Node.js 20+ and npm
- Redis (for Celery)
- An [OpenRouter](https://openrouter.ai/) API key

```bash
# Redis, if you don't already have it
sudo apt install redis-server   # or: brew install redis
redis-server &                  # or run it as a service
redis-cli ping                  # should print PONG
```

## 1. Backend

```bash
cd prometheus
uv sync                          # creates .venv and installs everything
source .venv/bin/activate
cp .env.example .env
```

Edit `.env`:
- `OPENROUTER_API_KEY` — required
- `OPENROUTER_MODEL` — **must be a tool-calling-capable model**. `google/gemini-2.5-flash`
  (the default) works. Many free-tier models on OpenRouter do not support tool
  calling at all and will fail with a clear error at chat time if you swap
  one in — check the model's page on OpenRouter for "tools" support first.
- Everything else has a working default for local dev (SQLite, local Chroma,
  DuckDuckGo web search with no key needed).

Set up the database and run the test suite to confirm the environment is sane:

```bash
alembic upgrade head
ruff check .
pytest
```

## 2. Background worker (Celery)

Document processing (parsing, chunking, embedding) and web crawling run
through Celery, not inline. Start a worker in its own terminal and leave it
running:

```bash
source .venv/bin/activate
celery -A prometheus.tasks.celery_app worker --loglevel=info
```

**Restart this worker whenever you change code under `src/prometheus/tasks/`
or anything it imports** (ingestion, retrieval, providers) — like any long-running
Python process, it doesn't pick up code changes on its own.

> **Known limitation:** the local Chroma vector store is single-process by
> design. If you're uploading multiple documents in quick succession and see
> a `"readonly database"` error, that's this — the worker retries
> automatically a few times, and it isn't a concern for normal single-user
> local development. See `plan.md` (Phase 4/15 notes) for the full
> explanation and the proper long-term fix (a Chroma server).

## 3. Backend API

```bash
source .venv/bin/activate
uvicorn prometheus.api.app:app --reload --port 8000
```

Confirm it's up:

```bash
curl http://127.0.0.1:8000/api/rag/health
# {"status":"ok","service":"prometheus-rag"}
```

Interactive API docs: http://127.0.0.1:8000/docs

## 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — the dev server proxies `/api/*` to the backend
on port 8000 (see `frontend/vite.config.ts`), so both need to be running.

To build for production: `npm run build` (outputs to `frontend/dist/`).

## 5. Try it end-to-end

Either through the UI (create a project in the sidebar, upload a `.pdf`/
`.docx`/`.pptx`/`.txt`, wait for it to show a document icon instead of a
spinner, then ask a question) or via the CLI:

```bash
research project create "My Project"
research document add <project-id> ./some_file.pdf
research document show <document-id>     # wait for status: READY
research chat ask <project-id> "What does this document say?"
```

See `plan.md` for the full command reference (projects, documents, search,
chat, crawl, eval) and what's been built in each phase.

## Everything running at once, for reference

| Process | Command | Port |
|---|---|---|
| Redis | `redis-server` | 6379 |
| Celery worker | `celery -A prometheus.tasks.celery_app worker --loglevel=info` | — |
| Backend API | `uvicorn prometheus.api.app:app --reload --port 8000` | 8000 |
| Frontend | `npm run dev` (in `frontend/`) | 5173 |

## Running tests

```bash
pytest              # full suite; fast, offline, no API key needed
ruff check .         # lint
research eval run    # live evaluation suite against the real LLM -- costs tokens, not in pytest
```

```bash
cd frontend
npm run build        # type-checks + bundles; closest thing to a frontend test suite today
```

## Troubleshooting

- **`ModuleNotFoundError: No module named 'prometheus'`** — you're likely
  running a system-aliased `python3` instead of the venv's. Use `python`
  (not `python3`) after `source .venv/bin/activate`, or check `which python3`
  for a shell alias overriding it.
- **Chat returns a "No endpoints found that support tool use" error** — your
  `OPENROUTER_MODEL` doesn't support tool calling. Switch models.
- **A newly uploaded document stays `UPLOADED` forever** — the Celery worker
  isn't running, or it's running stale code from before your last change
  (restart it).
- **`chromadb.errors.InternalError: ... Nothing found on disk`** — you ran
  two separate Python processes (e.g. a script and the API server, or two
  workers) writing to the same local Chroma store at once. Restart whichever
  process opened its connection first.
