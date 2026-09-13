# Showcase — Phase 1 status

A rehearsal-ready script for demoing what's built so far: the full data
layer & retrieval plumbing (README Phase 1), plus the OpenRouter LLM
provider swap. No agents or orchestration yet — that's Phase 2+.

## Before the demo

1. Commit any pending work so `git log` and the working tree are clean.
2. Run through this whole script once yourself beforehand — arXiv and
   Semantic Scholar occasionally rate-limit; OpenAlex has been the most
   reliable source in testing.
3. Make sure `.env` is filled in (`OPENROUTER_API_KEY`, `OPENALEX_MAILTO`)
   so nothing prompts mid-demo.
4. Activate the venv in your terminal: `source .venv/bin/activate`

---

## 1. Frame it — where this sits in the plan (30s)

Open [README.md](README.md), scroll to "Build phases". Point at the Phase 0
and Phase 1 checkboxes — Phase 1 is fully checked off. This gives the
audience the map before the details.

## 2. Architecture in one picture (1 min)

Open [docs/architecture.md](docs/architecture.md) — the Mermaid diagram
renders directly in GitHub/most markdown viewers. Point out where today's
work sits: the Retriever Agent's four stores (paper corpus, domain docs,
vector store, Findings DB) are exactly what got built — minus the "Agent"
wrapper around them, which is Phase 2.

## 3. Prove it's not vaporware — tests + lint (30s)

```bash
ruff check .
pytest -v
```

`tests/test_retrieval.py` passes for real (not skipped). `test_agents.py`
and `test_graph.py` are still honestly marked as skipped stubs — good
signal you're not overclaiming status.

## 4. Live: pull real papers from a live API (2 min)

```bash
rm -rf /tmp/demo_chroma
CHROMA_PERSIST_DIR=/tmp/demo_chroma python scripts/ingest_papers.py \
  --query "retrieval augmented generation" --max-results 3 --sources openalex
```

Narrate while it runs: fetches metadata from OpenAlex → dedupes across
sources → downloads each PDF → parses with PyMuPDF → chunks → embeds
(`sentence-transformers/all-MiniLM-L6-v2`) → writes into Chroma + the BM25
index.

**Other queries worth having ready**, in case you want a second round or
the first one returns thin results:
- `"large language model hallucination"`
- `"graph neural networks survey"`
- `"cross-encoder reranking"`

If you want to show arXiv/Semantic Scholar live too:

```bash
python scripts/ingest_papers.py --query "retrieval augmented generation" \
  --max-results 3 --sources arxiv
python scripts/ingest_papers.py --query "retrieval augmented generation" \
  --max-results 3 --sources semantic_scholar
```

Mention their stricter/keyed rate limits rather than risk a live failure —
that's an honest, not a weak, thing to say if one of them 429s.

## 5. Live: query it back out (1–2 min)

```bash
CHROMA_PERSIST_DIR=/tmp/demo_chroma python -c "
from prometheus.retrieval.hybrid_search import hybrid_search
from prometheus.retrieval.reranker import rerank, apply_recency_and_credibility_filters

question = 'does retrieval reduce hallucination in language models?'
hits = hybrid_search(question, top_k=5)
ranked = apply_recency_and_credibility_filters(rerank(question, hits))
for r in ranked[:3]:
    print(round(r['final_score'], 3), '-', r['text'][:100].replace(chr(10), ' '))
"
```

This is the payoff moment: BM25 + dense fusion → cross-encoder rerank →
recency/source-credibility scoring, on papers pulled live seconds ago.

**Other questions worth trying against the ingested corpus:**
- `"what are the limitations of dense retrieval alone?"`
- `"how does hybrid search combine BM25 and dense vectors?"`
- `"what is a cross-encoder reranker?"`

**Show routing logic too** — the Retriever's store-selection heuristic:

```bash
python -c "
from prometheus.retrieval.hybrid_search import route
print(route('have we looked at retrieval-augmented generation before?'))
print(route('what is the effect of chunk size on retrieval quality?'))
"
```

Expected: the first includes `findings_db` (recall-flavored phrasing), the
second is just `['paper_corpus', 'domain_docs']`.

## 6. Findings DB — the fourth data store (1 min)

```bash
rm -f /tmp/demo_findings.db
DATABASE_URL="sqlite:////tmp/demo_findings.db" python scripts/seed_findings_db.py --with-sample-data
```

Then show it's queryable:

```bash
DATABASE_URL="sqlite:////tmp/demo_findings.db" python -c "
from prometheus.findings import repository as repo
for r in repo.search_findings('retrieval'):
    print(r.status, '-', r.question)
"
```

Explain: this is the fourth data store — past reports + reasoning chains,
reused as context in later investigations. Not wired to agents yet
(Phase 2+), but the schema and read/write path exist and work today.

## 7. Close with what's next (30s)

Back to the README Phase 2 checklist: Planner / Researcher / Retriever /
Critic / Synthesizer agents, standalone, running against this retrieval
layer. Mention the OpenRouter switch briefly — cheaper model routing,
already wired into `config.py`, ready for when agent LLM calls start in
Phase 2.

---

## If something breaks live

Have tonight's dry-run output saved (screenshot or terminal log) as a
fallback you can show instead of re-running against a possibly
rate-limited API.

## Reference: everything runnable today

| What | Command |
|---|---|
| Lint | `ruff check .` |
| Tests | `pytest -v` |
| Ingest papers | `python scripts/ingest_papers.py --query "..." --max-results N` |
| Seed Findings DB | `python scripts/seed_findings_db.py --with-sample-data` |
| Query retrieval | see section 5 above |
| Query Findings DB | see section 6 above |

There's no single "run everything" entry point yet — Phase 2 (agents) and
Phase 3 (LangGraph orchestration) haven't been built. Once those land,
`app/streamlit_app.py`'s "Run investigation" button becomes that entry
point: type a question, it calls
`prometheus.graph.meta_orchestrator.run_investigation`, and everything
above runs underneath it automatically.
