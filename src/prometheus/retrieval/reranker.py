"""
Cross-encoder reranker: takes the union of BM25 + dense-vector hits and
re-scores (query, chunk) pairs jointly for a sharper final ranking.

Recency + source-credibility filtering/boosting happens after rerank, per
the proposal ("followed by ... filtering by recency and source
credibility").
"""
from __future__ import annotations

from datetime import UTC, datetime

from sentence_transformers import CrossEncoder

# Pinned cross-encoder: small, fast, strong baseline for passage reranking.
CROSS_ENCODER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Static credibility weight by source; unknown sources default to 1.0.
_SOURCE_CREDIBILITY = {
    "semantic_scholar": 1.1,
    "openalex": 1.05,
    "arxiv": 1.0,  # preprints, not peer-reviewed
    "domain_doc": 1.0,
}

_cross_encoder: CrossEncoder | None = None


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL_NAME)
    return _cross_encoder


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    pairs = [(query, c["text"]) for c in candidates]
    scores = _get_cross_encoder().predict(pairs)

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)

    return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)


def apply_recency_and_credibility_filters(
    candidates: list[dict],
    max_age_years: float | None = None,
) -> list[dict]:
    """Boosts each candidate's score by source credibility and, if a `year`
    is present in its metadata, drops anything older than `max_age_years`
    and applies a mild recency boost. Candidates without a `year` (e.g.
    domain docs) are kept as-is aside from the credibility boost."""
    current_year = datetime.now(UTC).year
    filtered = []

    for candidate in candidates:
        metadata = candidate.get("metadata", {})
        year = metadata.get("year")

        if max_age_years is not None and year is not None and (current_year - year) > max_age_years:
            continue

        base_score = candidate.get("rerank_score", candidate.get("score", 0.0))
        credibility = _SOURCE_CREDIBILITY.get(metadata.get("source") or metadata.get("source_type"), 1.0)
        recency_boost = 1.0
        if year is not None:
            recency_boost = 1.0 + max(0.0, 0.02 * (10 - min(10, current_year - year)))

        candidate["final_score"] = base_score * credibility * recency_boost
        filtered.append(candidate)

    return sorted(filtered, key=lambda c: c["final_score"], reverse=True)
