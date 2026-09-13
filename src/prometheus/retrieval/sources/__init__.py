"""Paper-source clients: arXiv, Semantic Scholar, OpenAlex."""
from prometheus.retrieval.sources.arxiv_client import search_arxiv
from prometheus.retrieval.sources.openalex_client import search_openalex
from prometheus.retrieval.sources.paper_record import PaperRecord
from prometheus.retrieval.sources.semantic_scholar_client import search_semantic_scholar

__all__ = [
    "PaperRecord",
    "search_arxiv",
    "search_openalex",
    "search_semantic_scholar",
]
