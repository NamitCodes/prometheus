"""
Hybrid search: combines BM25 lexical search with dense vector search, then
hands the merged candidate set to the reranker. Also owns the routing
logic that decides which store(s) a given sub-question should query.

The BM25 index is a flat JSONL file (kept alongside the Chroma persist dir)
of {id, text, metadata}, rebuilt into an in-memory rank_bm25 index lazily.
Fine for Phase 1-2 corpus sizes; revisit if it becomes a bottleneck.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from rank_bm25 import BM25Plus

from prometheus.config import settings
from prometheus.retrieval.vector_store import get_vector_store

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Sub-questions with this kind of language should also check the Findings DB
# for prior work, not just the paper/doc corpus.
_RECALL_PATTERNS = re.compile(
    r"\b(have we|did we|previously|prior (research|finding|work|investigation)|"
    r"already (looked|investigated|found)|earlier (report|finding))\b",
    re.IGNORECASE,
)


def _bm25_index_path() -> Path:
    path = Path(settings.CHROMA_PERSIST_DIR) / "bm25_index.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def add_to_bm25(chunks: list[dict]) -> None:
    """chunks: [{id, text, metadata}] -- appends to the flat BM25 corpus file."""
    if not chunks:
        return
    path = _bm25_index_path()
    with path.open("a", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps({"id": chunk["id"], "text": chunk["text"], "metadata": chunk.get("metadata", {})}))
            f.write("\n")


def remove_from_bm25(document_id: str) -> None:
    """Rewrites the JSONL corpus without entries for `document_id` (used when a
    document is deleted, so stale chunks don't linger in search results)."""
    remove_from_bm25_by_metadata({"document_id": document_id})


def remove_from_bm25_by_metadata(filters: dict) -> None:
    """Rewrites the JSONL corpus without entries matching every key/value in
    `filters` -- e.g. {"project_id": ...} to purge an entire deleted project,
    including web-crawled chunks that have no owning Document row to loop
    over individually."""
    if not filters:
        return
    path = _bm25_index_path()
    if not path.exists():
        return

    kept_lines = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            metadata = record.get("metadata", {})
            if not all(metadata.get(key) == value for key, value in filters.items()):
                kept_lines.append(stripped)

    path.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8")


def _load_bm25_corpus() -> list[dict]:
    """Load BM25 corpus from disk, deduplicating by (document_id, chunk_index).

    The JSONL file is append-only — re-ingesting the same document adds new
    entries without removing old ones.  We keep only the *last* record seen
    for each (document_id, chunk_index) key so stale entries from previous
    runs don't pollute the index.
    """
    path = _bm25_index_path()
    if not path.exists():
        return []
    seen: dict[tuple, dict] = {}  # key -> last-seen record
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            meta = record.get("metadata", {})
            # Stable fingerprint: prefer (document_id, chunk_index); fall back
            # to the chunk id so that records without metadata are still kept.
            key: tuple = (
                meta.get("document_id", ""),
                meta.get("chunk_index", record.get("id", "")),
            )
            seen[key] = record
    return list(seen.values())


def _matches_filters(metadata: dict, filters: dict | None) -> bool:
    if not filters:
        return True
    for key, val in filters.items():
        if metadata.get(key) != val:
            return False
    return True


def bm25_search(query: str, top_k: int = 20, filters: dict | None = None) -> list[dict]:
    corpus = _load_bm25_corpus()
    if filters:
        corpus = [doc for doc in corpus if _matches_filters(doc.get("metadata", {}), filters)]
    if not corpus:
        return []

    tokenized_corpus = [_tokenize(doc["text"]) for doc in corpus]
    bm25 = BM25Plus(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))

    ranked = sorted(zip(corpus, scores), key=lambda pair: pair[1], reverse=True)
    return [
        {"id": doc["id"], "text": doc["text"], "metadata": doc["metadata"], "score": float(score)}
        for doc, score in ranked[:top_k]
    ]


def dense_search(query: str, top_k: int = 20, filters: dict | None = None) -> list[dict]:
    from prometheus.retrieval.ingestion import (
        embed,  # local import: avoids a circular import at module load
    )

    query_embedding = embed([query])[0]
    hits = get_vector_store().query(query_embedding, top_k=top_k, filters=filters)
    return [
        {"id": hit["id"], "text": hit["text"], "metadata": hit["metadata"], "score": -hit["distance"]}
        for hit in hits
    ]


def hybrid_search(query: str, top_k: int = 20, filters: dict | None = None) -> list[dict]:
    """Merges BM25 + dense candidates via reciprocal rank fusion, deduped by id.

    A secondary deduplication pass by content hash guards against the case
    where two chunks with different UUIDs carry identical text (e.g. a file
    that was ingested twice via different code paths).
    """
    bm25_hits = bm25_search(query, top_k=top_k, filters=filters)
    dense_hits = dense_search(query, top_k=top_k, filters=filters)

    rrf_scores: dict[str, float] = {}
    by_id: dict[str, dict] = {}
    k = 60  # standard RRF constant

    for rank_list in (bm25_hits, dense_hits):
        for rank, hit in enumerate(rank_list):
            rrf_scores[hit["id"]] = rrf_scores.get(hit["id"], 0.0) + 1.0 / (k + rank + 1)
            by_id.setdefault(hit["id"], hit)

    merged = sorted(by_id.values(), key=lambda hit: rrf_scores[hit["id"]], reverse=True)
    for hit in merged:
        hit["score"] = rrf_scores[hit["id"]]

    # Secondary pass: drop chunks whose text is identical to a higher-ranked chunk.
    seen_text: set[int] = set()
    deduped: list[dict] = []
    for hit in merged:
        text_hash = hash(hit.get("text", "").strip())
        if text_hash not in seen_text:
            seen_text.add(text_hash)
            deduped.append(hit)

    return deduped[:top_k]



def route(sub_question: str) -> list[str]:
    """Decides which store(s) a sub-question should query.

    Default: paper corpus + domain docs (the vector store / BM25 index that
    ingestion.py populates). Recall-flavored questions ("have we looked at
    this before?") also route to the Findings DB.
    """
    stores = ["paper_corpus", "domain_docs"]
    if _RECALL_PATTERNS.search(sub_question):
        stores.append("findings_db")
    return stores
