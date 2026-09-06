#!/usr/bin/env python
"""
CLI script: fetch papers for a topic/query across arXiv, Semantic Scholar,
and OpenAlex, then run them through the ingestion pipeline.

Usage (once implemented):
    python scripts/ingest_papers.py --query "retrieval augmented generation" --max-results 50

TODO:
  - argparse: --query, --max-results, --sources (default: all three)
  - Fan out to prometheus.retrieval.sources.* search functions
  - Download PDFs where available, call prometheus.retrieval.ingestion.ingest_paper
  - De-dupe across sources (same paper via arXiv + Semantic Scholar + OpenAlex)
"""

if __name__ == "__main__":
    raise NotImplementedError("Phase 1: implement paper ingestion CLI")
