#!/usr/bin/env python
"""
CLI script: fetch papers for a topic/query across arXiv, Semantic Scholar,
and OpenAlex, then run them through the ingestion pipeline.

Usage:
    python scripts/ingest_papers.py --query "retrieval augmented generation" --max-results 20
    python scripts/ingest_papers.py --query "..." --sources arxiv openalex
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import httpx

from prometheus.retrieval.ingestion import ingest_paper
from prometheus.retrieval.sources import (
    PaperRecord,
    search_arxiv,
    search_openalex,
    search_semantic_scholar,
)

_SOURCE_FNS = {
    "arxiv": search_arxiv,
    "semantic_scholar": search_semantic_scholar,
    "openalex": search_openalex,
}


def _dedupe(records: list[PaperRecord]) -> list[PaperRecord]:
    """Same paper often shows up via multiple sources; prefer DOI, fall back
    to a normalized title, to avoid ingesting it twice."""
    seen: set[str] = set()
    deduped = []
    for record in records:
        key = record.doi.lower() if record.doi else record.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _download_pdf(url: str, dest_dir: Path) -> str | None:
    try:
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"  skip (download failed: {exc!r})")
        return None

    dest = dest_dir / f"{abs(hash(url))}.pdf"
    dest.write_bytes(response.content)
    return str(dest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--sources", nargs="+", choices=list(_SOURCE_FNS), default=list(_SOURCE_FNS))
    args = parser.parse_args()

    all_records: list[PaperRecord] = []
    for source in args.sources:
        try:
            results = _SOURCE_FNS[source](args.query, max_results=args.max_results)
        except httpx.HTTPError as exc:
            print(f"{source}: search failed ({exc!r}), skipping")
            continue
        print(f"{source}: {len(results)} results")
        all_records.extend(results)

    records = _dedupe(all_records)
    print(f"{len(records)} unique papers after dedup")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for record in records:
            if not record.pdf_url:
                print(f"skip (no PDF): {record.title[:60]}")
                continue

            pdf_path = _download_pdf(record.pdf_url, tmp_path)
            if pdf_path is None:
                continue

            print(f"ingesting: {record.title[:60]}")
            ingest_paper(pdf_path, source_id=f"{record.source}:{record.source_id}")


if __name__ == "__main__":
    main()
