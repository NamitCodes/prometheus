# Prometheus — Implemented RAG Features

## Current Status

Prometheus currently provides a working **local document RAG pipeline** with optional **OpenAlex academic evidence**.

---

## 1. Local PDF RAG ✅

Supports:

- PDF parsing with page-aware metadata
- Structure-aware chunking
- Dense embeddings
- ChromaDB vector storage
- BM25 retrieval
- Hybrid retrieval using RRF
- Cross-encoder reranking
- Grounded LLM generation via OpenRouter
- Page/source citations
- Document-level scoping
- Insufficient-context handling

### Test

```powershell
python scripts\demo_rag.py --live --file "PATH_TO_PDF" --question "What does this paper propose?"
```

Example:

```powershell
python scripts\demo_rag.py --live --file "C:\Users\tatha\OneDrive\Desktop\resources\26-0434.pdf" --question "What does this paper propose?"
```

---

## 2. OpenAlex Academic Search ✅

Prometheus can query OpenAlex and retrieve academic `PaperRecord`s containing:

* Title
* Authors
* Abstract
* Publication year
* DOI
* OpenAlex URL
* PDF URL

### Test

```powershell
python -c "from prometheus.retrieval.sources.openalex_client import search_openalex; r=search_openalex('neural operators', max_results=3); [print(f'{i+1}. {x.title} ({x.year}) | {x.doi}') for i,x in enumerate(r)]"
```

---

## 3. Local RAG + OpenAlex Evidence 🟡

Optional academic mode combines:

```text
Local PDF evidence
        +
OpenAlex metadata/abstract
        ↓
      LLM
        ↓
Grounded combined answer
```

OpenAlex is **disabled by default**.

### Test

```powershell
python scripts\demo_rag.py --live --academic --file "PATH_TO_PDF" --question "What research exists on neural operators?"
```

---

## 4. OpenAlex PDF → RAG ⬜

Direct RAG over PDFs discovered through OpenAlex is **not yet implemented as a clean query-time workflow**.

The existing OpenAlex ingestion plumbing can download and ingest PDFs, but this is currently a separate/batch path.

---

## 5. Context-Aware Academic Query Expansion ⬜

Not yet implemented.

Planned flow:

```text
"What other research is related to this topic?"
                    ↓
        Identify PDF topic
                    ↓
          "neural operators"
                    ↓
              OpenAlex
                    ↓
          Relevant papers
```

---

## Verification

Run the complete test suite:

```powershell
pytest -q
```

Run Ruff:

```powershell
ruff check .
```

---

## Current RAG Architecture

```text
                ┌─────────────────┐
                │   User Query    │
                └────────┬────────┘
                         ↓
              ┌─────────────────────┐
              │ Local Document RAG  │
              └──────────┬──────────┘
                         ↓
              Parse → Chunk → Embed
                         ↓
                Chroma + BM25
                         ↓
                    RRF + Rerank
                         ↓
                  Grounded LLM
                         ↑
                         │
             Optional OpenAlex
             Academic Evidence
```

**Implemented:** Local PDF RAG + OpenAlex academic evidence/search

**Not implemented:** OpenAlex PDF RAG + automatic topic/query expansion
