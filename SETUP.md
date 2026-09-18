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
- Everything else has a working default for local dev (SQLite, DuckDuckGo web
  search with no key needed). Chroma defaults to embedded mode, which is fine
  for `pytest` and one-off CLI use, but **not** once the API and a Celery
  worker run together — set `CHROMA_SERVER_URL` per step 2 for that.

Set up the database and run the test suite to confirm the environment is sane:

```bash
alembic upgrade head
ruff check .
pytest
```

## 2. Chroma server

The vector store's embedded mode (`chromadb.PersistentClient`) only
supports **one process** touching it at a time. As soon as you run the
backend API and a Celery worker together (or `uvicorn --reload`, which is
itself two processes), you will eventually hit a corruption-flavored error
(`"readonly database"`, `"Nothing found on disk"`, `"Error finding id"`).

Run Chroma as an actual server instead — required for anything beyond a
single one-off script:

```bash
source .venv/bin/activate
chroma run --path ./chroma_data --port 8001
```

Then set in `.env`:

```bash
CHROMA_SERVER_URL=localhost:8001
```

Leave this running alongside everything else below.

## 3. Background worker (Celery)

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

## 4. Backend API

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

## 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — the dev server proxies `/api/*` to the backend
on port 8000 (see `frontend/vite.config.ts`), so both need to be running.

To build for production: `npm run build` (outputs to `frontend/dist/`).

## 6. Try it end-to-end

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
| Chroma server | `chroma run --path ./chroma_data --port 8001` | 8001 |
| Celery worker | `celery -A prometheus.tasks.celery_app worker --loglevel=info` | — |
| Backend API | `uvicorn prometheus.api.app:app --reload --port 8000` | 8000 |
| Frontend | `npm run dev` (in `frontend/`) | 5173 |

## Running tests

```bash
pytest              # full suite; fast, offline, no API key needed
ruff check .         # lint
research eval run    # live evaluation suite against the real LLM -- costs tokens, not in pytest
```

`pytest` is isolated from your running stack: `tests/conftest.py` forces every
test onto embedded Chroma in its own temp dir, ignoring `CHROMA_SERVER_URL`
from `.env`, so it's safe to run while the Chroma server, worker, and API are
up and it won't write to your real data.

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
- **`chromadb.errors.InternalError`** (`"Nothing found on disk"`, `"Error
  finding id"`, `"readonly database"`) — you're running Chroma in embedded
  mode (`CHROMA_SERVER_URL` unset) with more than one process touching it.
  Set up the Chroma server (step 2) — that's the actual fix, not a restart.
  If you already have data in `./chroma_data` from before making that
  switch, it isn't lost: `chroma run` reads the same directory fine.
