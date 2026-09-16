from __future__ import annotations

from collections.abc import Sequence

from prometheus.rag.models import AcademicSourceRecord, SourceRecord
from prometheus.retrieval.sources.paper_record import PaperRecord


def build_context(ranked_chunks: Sequence[dict]) -> tuple[str, list[SourceRecord]]:
    """Format ranked candidate chunks into numbered context blocks and structured SourceRecords.

    Parameters
    ----------
    ranked_chunks : Sequence[dict]
        List of chunk dicts returned by the retrieval and reranking layer.
        Expected keys: id, text, metadata, score (or rerank_score/final_score).

    Returns
    -------
    tuple[str, list[SourceRecord]]
        1. Context string ready for prompt injection with citations [1], [2], ...
        2. List of typed SourceRecords preserving full document provenance.
    """
    if not ranked_chunks:
        return "", []

    context_blocks: list[str] = []
    sources: list[SourceRecord] = []

    for idx, chunk in enumerate(ranked_chunks, start=1):
        metadata = chunk.get("metadata", {}) or {}
        text = chunk.get("text", "").strip()
        chunk_id = chunk.get("id", f"chunk-{idx}")
        score = chunk.get("final_score", chunk.get("rerank_score", chunk.get("score")))

        doc_id = metadata.get("document_id") or metadata.get("source_id") or metadata.get("project_id") or "unknown"
        filename = metadata.get("filename") or metadata.get("url") or "document"
        file_type = metadata.get("file_type")
        page_num = metadata.get("page_number")
        slide_num = metadata.get("slide_number")
        heading = metadata.get("heading")

        # Build human-readable location tag
        location_parts = []
        if page_num is not None:
            location_parts.append(f"Page {page_num}")
        if slide_num is not None:
            location_parts.append(f"Slide {slide_num}")
        if heading:
            location_parts.append(f"Section: '{heading}'")

        location_str = f" ({', '.join(location_parts)})" if location_parts else ""

        # Format context passage
        passage_header = f"[{idx}] Source: {filename}{location_str} [DocID: {doc_id}]"
        context_blocks.append(f"{passage_header}\n{text}")

        # Create structured source record
        sources.append(
            SourceRecord(
                citation_index=idx,
                document_id=str(doc_id),
                filename=str(filename),
                file_type=file_type,
                page_number=page_num,
                slide_number=slide_num,
                heading=heading,
                chunk_id=str(chunk_id),
                score=float(score) if score is not None else None,
                text_snippet=text,
            )
        )

    full_context_str = "\n\n".join(context_blocks)
    return full_context_str, sources


_ACADEMIC_LABELS = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")


def build_academic_context(
    records: Sequence[PaperRecord],
) -> tuple[str, list[AcademicSourceRecord]]:
    """Format OpenAlex PaperRecords into labeled academic context blocks and typed AcademicSourceRecords.

    Parameters
    ----------
    records : Sequence[PaperRecord]
        List of PaperRecord objects returned by search_openalex().

    Returns
    -------
    tuple[str, list[AcademicSourceRecord]]
        1. Formatted academic literature context string labeled with [A], [B], ...
        2. List of typed AcademicSourceRecords preserving full bibliographic metadata.
    """
    if not records:
        return "", []

    context_blocks: list[str] = []
    academic_sources: list[AcademicSourceRecord] = []

    for idx, paper in enumerate(records):
        label = _ACADEMIC_LABELS[idx] if idx < len(_ACADEMIC_LABELS) else f"Ref-{idx + 1}"
        authors_str = ", ".join(paper.authors) if paper.authors else "Unknown Authors"
        year_str = str(paper.year) if paper.year is not None else "n.d."
        doi_or_url = paper.doi or paper.url or "N/A"
        abstract_text = paper.abstract.strip() if paper.abstract and paper.abstract.strip() else "No abstract provided."

        header = (
            f"[{label}] Paper: \"{paper.title}\"\n"
            f"    Authors: {authors_str} ({year_str})\n"
            f"    DOI / Link: {doi_or_url} [OpenAlex ID: {paper.source_id}]"
        )
        context_blocks.append(f"{header}\n    Abstract: {abstract_text}")

        academic_sources.append(
            AcademicSourceRecord(
                citation_label=label,
                source=paper.source,
                source_id=paper.source_id,
                title=paper.title,
                authors=paper.authors,
                year=paper.year,
                doi=paper.doi,
                url=paper.url,
                abstract=paper.abstract,
            )
        )

    return "\n\n".join(context_blocks), academic_sources

