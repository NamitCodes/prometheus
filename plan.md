# Prometheus — AI Research Workspace: Build Plan

Full architectural rationale, tech choices, and design rules live in the
project discussion this plan came from (a NotebookLM-like research
workspace: projects, documents, semantic retrieval, web access, LangGraph
orchestration, CLI-first, React later). This file tracks **phases and
status** so anyone can see what's done without re-reading the whole thing.

Core principle: business logic depends on application-level interfaces
(`LLMProvider`, `EmbeddingProvider`, `VectorStore`, `ObjectStorageProvider`,
`WebSearchProvider`, ...), never directly on a specific vendor SDK.

Relationship to the *older* Prometheus vision (multi-agent adversarial
debate loop — Planner/Critic/Synthesizer, Meta-Orchestrator) documented in
`docs/architecture.md`: undecided. `agents/` and `graph/` are left as-is
for now; this plan does not build on them. Revisit before Phase 9.

---

## Phase 1 — Repository assessment ✅

- [x] Inspect existing repository, identify reusable code
- [x] Produce implementation assessment (see conversation history / commit messages)

**Findings:** async SQLAlchemy, an `LLMProvider`-equivalent abstraction
(`llm/base.py`, `llm/openrouter.py`, `llm/mock.py`, `llm/service.py`), a
working single-document RAG pipeline (`rag/`), retrieval layer
(`retrieval/`: source clients, hybrid search, vector store, reranker), and
a FastAPI scaffold (`api/app.py`) already existed and are being reused
rather than rebuilt.

## Phase 2 — CLI foundation ✅

- [x] Project structure refinements (`db/`, `services/`, `cli/` packages)
- [x] Configuration (`APP_DATABASE_URL` added to `config.py` + `.env.example`)
- [x] SQLite + async SQLAlchemy setup (`db/session.py`, separate `data/app.db`)
- [x] Alembic migrations (hand-written async `env.py`, first migration generated + applied)
- [x] CLI entry point (Typer, `research` console script)
- [x] `research project create / list / delete`
- [x] `research document list`

Acceptance criteria met: `research project create/list` and
`research document list` all work without the frontend.

## Phase 3 — Storage and document management ✅

- [x] Project model
- [x] Document model
- [x] Document version model
- [x] Local file storage (`ObjectStorageProvider` + local implementation, path-traversal guarded)
- [x] `research document add` (upload/add command)
- [x] Document metadata, status (`UPLOADED/PROCESSING/INDEXING/READY/FAILED`)
- [x] `research document delete`
- [x] `research document list`, `research document show`

No AI chat yet.

## Phase 4 — PDF processing ✅

- [x] PDF/DOCX/PPTX/TXT → text extraction → chunking → embedding (reused `retrieval/parsers.py`, `retrieval/ingestion.py::ingest_document` as-is)
- [x] Run processing through Celery (`tasks/celery_app.py`, `tasks/document_tasks.py::process_document`), only `document_id` crosses the Redis queue
- [x] Status transitions UPLOADED → PROCESSING → INDEXING → READY/FAILED, with error message stored on failure
- [x] `research document show <id>` inspects status; `research document reindex <id>` re-enqueues processing
- [x] `research document add` enqueues automatically after upload

Verified live: real Redis + real `celery -A prometheus.tasks.celery_app worker`,
CLI upload → async status transition to READY → chunk confirmed retrievable
via `hybrid_search` with correct `document_id`/`project_id` metadata.
Tests use Celery's `task_always_eager` (no broker needed).

**Known issue found live, partially mitigated**: ChromaDB's embedded
`PersistentClient` is single-process by design. Celery's default worker pool
runs multiple concurrent processes (prefork), and two documents processed at
the same moment in different worker processes can collide with a
`"readonly database"` / `"database is locked"` error from Chroma's storage
engine. `process_document` now detects this specific error and retries (up
to 4x, 5/10/15/20s backoff) instead of failing the document outright — this
handles the common case where the other writer finishes quickly. It does
**not** fully solve the underlying architectural issue: under sustained
concurrent load, retries could still exhaust. Proper fix is one of (a) run
Chroma as a server (`chroma run`) and switch to `HttpClient`, which is
designed for multi-process access, or (b) pin the document-processing worker
to a single process (`celery ... --concurrency=1` or `--pool=solo`).
Deferred for now since single-user local dev rarely triggers true
concurrent writes.

## Phase 5 — ChromaDB ✅

- [x] `VectorStore` interface + Chroma implementation (already existed) — `add` / `query` / `delete` / `delete_by_metadata`
- [x] Metadata filtering, including combined multi-key filters (`project_id` + `document_id`)
- [x] Deleting a document now purges its chunks from both Chroma and the BM25 index (`vector_store.delete_by_metadata`, `hybrid_search.remove_from_bm25`) — previously a leak: deleted docs stayed searchable

**Bug found and fixed:** newer ChromaDB rejects a `where` filter with more
than one top-level key (`{"a": 1, "b": 2}` → `ValueError`); needs an
explicit `{"$and": [...]}`. Only surfaced once two filters were combined
for the first time (project + document scoping below). Fixed in
`vector_store._build_where`.

## Phase 6 — Embeddings ⬜

- [x] Embedding generation already exists (`retrieval/ingestion.py::embed`, pinned `all-MiniLM-L6-v2`) — reused as-is
- [ ] Formal `EmbeddingProvider` protocol/abstraction (currently a bare function, not swappable behind an interface yet)
- [ ] Batching/retry hardening for very large documents

## Phase 7 — Retrieval ✅

- [x] `services/retrieval.py::search_knowledge(query, *, project_id, document_id=None, limit=10)` — query → hybrid search → rerank → recency/credibility scoring → top-k, returning structured `RetrievedChunk` (provenance: document_id, project_id, filename, page/slide number, score)
- [x] `project_id` is a required keyword argument merged into filters *after* any caller input — cross-project leakage isn't just tested against, it's structurally unrequestable through this API
- [x] `research search knowledge <project_id> <query> [--document] [--limit]` CLI command
- [x] Tests: project scoping, document+project combined filtering, no cross-project leakage, empty-result behavior, deletion purges the index (all passing; verified live with two real projects sharing near-identical wording)

## Phase 8 — OpenRouter provider ✅

- [x] `llm/openrouter.py` (custom `BaseLLMClient`, used by `rag/pipeline.py`) reused as-is — plain generation only
- [x] For LangGraph tool-calling, used `langchain_openai.ChatOpenAI` pointed at OpenRouter instead (already a dependency) — LangGraph needs a `BaseChatModel` with `.bind_tools()`, which the custom client doesn't implement
- [x] **Capability gap found live**: the model configured in `.env` (`z-ai/glm-5.2:free`) has *no* tool-calling-capable endpoint on OpenRouter at all — confirms new-plan.md section 14's concern is real, not theoretical. CLI now catches this and prints an actionable message instead of a stack trace. Switched default to `google/gemini-2.5-flash`, verified live.

## Phase 9 — Basic LangGraph ✅

- [x] Graph built in a new `workflow/` package (`workflow/state.py`, `workflow/tools.py`, `workflow/graph.py`) — kept separate from `agents/`/`graph/`, which remain untouched stubs for the older debate-loop vision. **Decision**: don't build on them; that vision's fate stays undecided but nothing here depends on or blocks it.
- [x] `START → agent → [tool_calls?] → tools → agent → ... → END`, `knowledge_search` tool scoped by `project_id` via closure (never an LLM-fillable parameter, per section 21)
- [x] Citations extracted from tool-call results in message history, not trusted from model prose (section 28)
- [x] `research chat ask <project_id> "<question>"` — answer + structured `Sources:` list
- [x] Tests via a scripted fake `BaseChatModel` (no live LLM needed) + a live end-to-end run: real OpenRouter model called `knowledge_search`, retrieved the right chunk, answered correctly with citation

## Phase 10 — CLI research workflow ✅

- [x] `workflow/graph.py::ChatSession` — threads full message history across turns through the same compiled graph (no LangGraph checkpointer needed; state lives in the session object, not yet persisted to the app DB — that's section 27, still open)
- [x] `research chat start <project_id>` — interactive REPL, `exit`/`quit`/Ctrl-D/Ctrl-C to leave, per-turn error boundary (one bad LLM call doesn't kill the session)
- [x] Citations correctly isolated per turn (a turn with no new tool call carries no citations, even if the session has prior ones)
- [x] Verified live: multi-turn conversation via real OpenRouter, second turn's answer and citations independent of the first

## Phase 11 — Web access ✅

- [x] `WebSearchProvider`, `WebFetcher`, `WebCrawlerProvider` interfaces (`providers/web/`)
- [x] `web_search`, `web_fetch` LangGraph tools, bound alongside `knowledge_search` in the same agent
- [x] `web_crawl` as a persistent Celery task (`crawl_and_index`) rather than a synchronous tool -- crawling is slow/unbounded, matches new-plan.md's Celery-vs-LangGraph split (section 6)
- [x] `research crawl url <project_id> <start_url> [--max-pages] [--max-depth]`
- [x] SSRF protections (section 58): scheme allowlist, DNS-resolved IP checked against private/loopback/link-local/reserved/multicast ranges (covers the 169.254.169.254 cloud metadata case), re-validated on every redirect hop, response size capped, crawl bounded by page count + depth + same-domain only
- [x] Citations extended to web sources: a `web_search` hit or a `web_fetch`'d page both count -- **bug found live**: initially only `web_fetch` produced a citation, so a model answering straight from a search snippet (common, since Gemini often didn't bother fetching) silently returned zero sources despite genuinely using one. Fixed to treat both as citations, matching how `knowledge_search` never required a second "fetch" step either.
- [x] Verified live: real DuckDuckGo search + real page fetch + real crawl-and-index of example.com, all through a live OpenRouter model with correct citations

Web pages indexed via crawl don't get a `Document` row in the app DB (no
local file to track) -- they're retrievable/citable but won't show up in
`research document list`. Acceptable simplification for this phase; revisit
if that gap matters later.

**Search provider decision**: DuckDuckGo (via the `ddgs` package), not Tavily
or Brave, because the user doesn't have a card to sign up for either paid-tier
provider. This is a **known temporary tradeoff** -- DuckDuckGo has no official
API; `ddgs` scrapes DDG's HTML/lite endpoints, which can break or get
rate-limited without notice. It's kept behind the `WebSearchProvider`
interface specifically so swapping in Brave Search (real free tier, no card
required, just signup) later is a one-file change, not a rewrite.
**TODO: replace with Brave Search API once an account is set up.**

## Phase 12 — Routing ✅ (satisfied by design, not a separate step)

- [x] **Decision**: no separate router node. The single agent in `workflow/graph.py` already has `knowledge_search`, `web_search`, and `web_fetch` bound together and decides per-question which (if any) to call -- this already satisfies "don't assume every question needs document retrieval / web search" without a duplicate classification step. Revisit as a real separate node only if it's needed for (a) cost control -- skipping tool binding entirely for obviously-general questions, or (b) dispatching to a genuinely different specialized agent/graph, once one exists.

## Phase 13 — Combined research workflow ✅

- [x] Already true by construction: the one agent can call `knowledge_search` and `web_search`/`web_fetch` in the same turn, synthesize across both, and cite both -- no separate wiring needed since Phase 11.
- [x] Verified live with a question that genuinely required both a project's uploaded document and external web content: model called both tool families in one turn and produced a synthesized answer with both a `document` and a `web` citation.

## Phase 14 — Evaluation ✅

- [x] `evaluation/dataset.py` + `evaluation/eval_runner.py` -- new, purpose-built for the Phase 9-13 chat workflow (left the old-vision `ragas_eval.py`/`llm_judge.py` stubs untouched; they target hypothesis/synthesis rubric grading, a different concern)
- [x] `research eval run` CLI command, non-zero exit on any failure (CI-gateable)
- [x] Checks routing correctness both directions: tool used when expected AND *not* used when not expected (over-triggering web search is treated as a failure, not just under-triggering)
- [x] Checks answer grounding via **fabricated facts** ("Zylorex-9 protocol", "Quintavane sensor") that cannot exist in the model's training data -- a correct answer is only possible via real `knowledge_search` grounding, no LLM-judge needed for this class of case
- [x] Live LLM eval, deliberately kept out of the default `pytest` run (costs tokens, not fully deterministic); creates and cleans up throwaway `eval-*` projects
- [x] Verified live: 4/4 cases pass against the real workflow; confirmed a deliberately-wrong expectation is correctly caught as a failure

**Bug found and fixed while wiring this up**: `delete_project` deleted DB
rows but never purged the vector store/BM25 index -- every project deletion
(and thus every eval run) would have leaked orphaned chunks forever,
including web-crawled chunks with no `Document` row to loop over at all.
Fixed by purging both stores directly by `project_id` in one shot
(`vector_store.delete_by_metadata`, new `hybrid_search.remove_from_bm25_by_metadata`).

## Phase 15 — FastAPI backend ✅

- [x] Scaffold exists (`api/app.py`, RAG query/ingest endpoints) -- kept as-is, not migrated, serves the original single-document RAG feature
- [x] Versioned `/api/v1` routes (`api/routes/{projects,documents,search,chat}.py`), all calling the same `prometheus.services.*` functions the CLI uses -- no duplicated logic
- [x] Projects: full CRUD. Documents: upload/list/get/reindex/delete. Search: same `search_knowledge`. Chat: same `ask()`, non-streaming (SSE is Phase 16)
- [x] Blocking-call fix: `ask()` and the sync graph invocation are dispatched via `asyncio.to_thread` so a slow LLM call doesn't stall the event loop for other requests
- [x] **Real bug found and fixed**: file uploads used `tempfile.NamedTemporaryFile`, which gives the file a random name -- since `add_document()` takes the filename from the path it's handed, every API-uploaded document's `filename` field was the random temp name, not the real one. Fixed by writing into a `TemporaryDirectory` under the real filename instead.
- [x] **Security fix alongside it**: `file.filename` is client-controlled: a crafted `../../../etc/evil.txt` would have escaped the temp directory. Sanitized via `Path(...).name`, with an explicit check for the `".."`-itself edge case (`Path("..").name == ".."`, `.name` alone doesn't catch it)
- [x] Conversation persistence/CRUD (new-plan.md section 27) intentionally **not** built -- still open, same gap as CLI's `ChatSession` (in-memory only)
- [x] 8 new tests (TestClient-driven, including the path-traversal case) + verified live: real uvicorn server, real project/document/search/chat round trip, live path-traversal attempt confirmed harmless on disk

Retesting note for future-self: don't run a one-off script against the same
Chroma persist dir while a server process already has it open -- same
single-process limitation as Phase 4, hit again here while verifying (fixed
by restarting the server after out-of-process writes, not a product bug).

## Phase 16 — Streaming backend ✅

- [x] `workflow/graph.py::astream_chat()` -- async generator over `compiled.astream_events(..., version="v2")`, emitting exactly the event vocabulary new-plan.md section 29 calls for: `agent_started`, `tool_started`/`tool_finished`, `token`, `citation`, `agent_finished`, `error`. No raw chain-of-thought exposed.
- [x] `GET /api/v1/projects/{id}/chat/stream?question=...` -- SSE (`text/event-stream`), GET+query-param rather than POST+body because browsers' `EventSource` API only supports GET with no custom body
- [x] Citation logic refactored into a shared `_citations_from_tool_result()` helper used by both the sync path (`_extract_citations`, over full `ToolMessage`s) and the new streaming path (per `on_tool_end` event) -- one source of truth for what counts as a citation
- [x] **Bug found and fixed**: citation events were built as `{"type": "citation", **citation}` -- since each citation dict already carries its own `"type"` key (`"document"`/`"web"`), the spread silently clobbered the event-type marker, so a consumer checking `event["type"] == "citation"` would never match. Fixed by nesting (`{"type": "citation", "citation": citation}`) instead of spreading.
- [x] **Robustness gap found and fixed**: if the underlying chat model doesn't implement true token streaming (`on_chat_model_stream` never fires -- true of any model exposing only `_generate`), `agent_finished` would report an empty answer despite the model genuinely answering. Added an `on_chat_model_end` fallback that captures the last non-empty AI message content.
- [x] Verified live end-to-end: real curl against a real running server, real OpenRouter model, correct SSE framing, correct event sequence (`agent_started` → `tool_started` → `tool_finished` → `citation` → `token`×N → `agent_finished`), real token-by-token streaming
- [x] Test uses the scripted (non-streaming) fake model specifically to exercise the `on_chat_model_end` fallback path, not just the happy path

## Phase 17 — React frontend ⬜

- [ ] Not started. Begins only once the CLI + backend definition-of-done criteria are met.

---

## Definition of done before frontend work begins

- [ ] SQLite schema and migrations work
- [ ] ChromaDB persistence works (project-scoped)
- [ ] Document ingestion is asynchronous (Celery)
- [ ] Embedding generation is asynchronous
- [ ] Retrieval tests pass
- [ ] OpenRouter provider works
- [ ] LangGraph workflow works
- [ ] CLI chat works
- [ ] Citations are structured
- [ ] Project/document boundaries are enforced
- [ ] Tests do not require paid APIs by default
- [ ] Application runs without React
