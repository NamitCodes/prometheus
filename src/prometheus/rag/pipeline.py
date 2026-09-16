"""
End-to-end RAG orchestrator for Prometheus.

Coordinates:
User Question -> Hybrid Search -> Cross-Encoder Rerank -> Grounded Context -> LLM Generation -> Answer + Sources.
"""
from __future__ import annotations

import logging

from prometheus.llm import BaseLLMClient, get_llm_client
from prometheus.rag.context import build_academic_context, build_context
from prometheus.rag.models import AcademicSourceRecord, RagResult
from prometheus.rag.prompts import RAG_SYSTEM_PROMPT, build_rag_user_prompt
from prometheus.retrieval import hybrid_search, reranker
from prometheus.retrieval.sources.openalex_client import search_openalex

logger = logging.getLogger(__name__)

INSUFFICIENT_CONTEXT_MESSAGE = (
    "The provided documents do not contain enough information to answer this question."
)


def query_rag(
    question: str,
    document_id: str | None = None,
    top_k: int = 5,
    llm_client: BaseLLMClient | None = None,
    include_academic_evidence: bool = False,
    openalex_max_results: int = 3,
) -> RagResult:
    """Execute the full RAG pipeline for a user question.

    Parameters
    ----------
    question : str
        The query asked by the user.
    document_id : str | None
        Optional document/notebook identifier. If supplied, search is isolated
        strictly to this document.
    top_k : int
        Number of top reranked chunks to include as evidence context (default: 5).
    llm_client : BaseLLMClient | None
        Optional LLM client instance (e.g. MockLLMClient for testing).
        If None, uses the globally configured OpenRouter client.
    include_academic_evidence : bool
        When True, additionally queries OpenAlex for up to `openalex_max_results`
        academic literature records (default: False).
    openalex_max_results : int
        Maximum number of academic papers to retrieve from OpenAlex when enabled (default: 3).

    Returns
    -------
    RagResult
        Contains the synthesized answer, structured sources, academic sources (if enabled),
        retrieved chunks, and sufficient-context indicator.
    """
    clean_query = (question or "").strip()
    if not clean_query:
        raise ValueError("Question cannot be empty or whitespace-only.")

    # 1. Optional External Academic Evidence Retrieval (OpenAlex)
    academic_sources: list[AcademicSourceRecord] = []
    academic_context_str: str | None = None
    if include_academic_evidence:
        try:
            logger.info(f"Querying OpenAlex for academic evidence (max_results={openalex_max_results})...")
            academic_records = search_openalex(query=clean_query, max_results=openalex_max_results)
            if academic_records:
                academic_context_str, academic_sources = build_academic_context(academic_records)
                logger.info(f"Retrieved {len(academic_sources)} academic records from OpenAlex.")
            else:
                logger.info("OpenAlex search returned 0 records.")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"Failed to fetch OpenAlex academic evidence (proceeding with local evidence only): {exc}"
            )

    # 2. Local Retrieval: Dense + BM25 via Hybrid Search
    filters = {"document_id": document_id} if document_id else None
    # Retrieve a slightly wider pool of candidates for the reranker
    retrieval_limit = max(top_k * 3, 15)
    candidates = hybrid_search.hybrid_search(
        query=clean_query,
        top_k=retrieval_limit,
        filters=filters,
    )

    if not candidates and not academic_context_str:
        logger.info(f"No candidates retrieved for query '{clean_query}'.")
        return RagResult(
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            sources=[],
            academic_sources=[],
            retrieved_chunks=[],
            has_sufficient_context=False,
        )

    # 3. Reranking: Cross-Encoder joint scoring on local candidates
    if candidates:
        reranked = reranker.rerank(query=clean_query, candidates=candidates)
        scored_candidates = reranker.apply_recency_and_credibility_filters(reranked)
        selected_chunks = scored_candidates[:top_k]
        context_str, sources = build_context(selected_chunks)
    else:
        selected_chunks = []
        context_str = ""
        sources = []

    if not context_str.strip() and not academic_context_str:
        return RagResult(
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            sources=[],
            academic_sources=[],
            retrieved_chunks=selected_chunks,
            has_sufficient_context=False,
        )

    # 4. Assemble Grounded Prompt (Dual-evidence if academic context present)
    user_prompt = build_rag_user_prompt(
        question=clean_query,
        context_str=context_str,
        academic_context_str=academic_context_str,
    )

    # 5. LLM Generation
    client = llm_client or get_llm_client()
    logger.info(
        f"Calling LLM for query: '{clean_query[:50]}...' with {len(sources)} local sources "
        f"and {len(academic_sources)} academic sources"
    )
    answer = client.generate(
        prompt=user_prompt,
        system_prompt=RAG_SYSTEM_PROMPT,
        temperature=0.0,
    )

    # 6. Check if LLM itself determined context is insufficient
    has_sufficient = INSUFFICIENT_CONTEXT_MESSAGE.lower() not in answer.lower()

    return RagResult(
        answer=answer,
        sources=sources,
        academic_sources=academic_sources,
        retrieved_chunks=selected_chunks,
        has_sufficient_context=has_sufficient,
    )
