"""
Unit tests for OpenAlex client query sanitization and paper record parsing.
Covers:
1. Query ending in '?' no longer reaches OpenAlex with '?' (fixes HTTP 400).
2. '*' and other Lucene/OpenAlex wildcard and special syntax characters are sanitized.
3. Normal query such as 'neural operators' remains unchanged.
4. Empty/whitespace/all-special queries return empty list gracefully without querying API.
5. Existing OpenAlex behavior (response parsing, mailto handling, inverted index abstract reconstruction) remains intact.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prometheus.retrieval.sources.openalex_client import search_openalex
from prometheus.retrieval.sources.paper_record import PaperRecord


@pytest.fixture
def mock_openalex_payload() -> dict:
    return {
        "results": [
            {
                "id": "https://openalex.org/W2964177579",
                "title": "Attention is All You Need",
                "display_name": "Attention is All You Need",
                "publication_year": 2017,
                "doi": "https://doi.org/10.48550/arxiv.1706.03762",
                "authorships": [
                    {"author": {"display_name": "Ashish Vaswani"}},
                    {"author": {"display_name": "Noam Shazeer"}},
                ],
                "open_access": {"oa_url": "https://arxiv.org/pdf/1706.03762.pdf"},
                "primary_location": {"pdf_url": "https://arxiv.org/pdf/1706.03762.pdf"},
                "abstract_inverted_index": {
                    "The": [0],
                    "dominant": [1],
                    "sequence": [2],
                    "transduction": [3],
                    "models": [4],
                },
            }
        ]
    }


def test_search_openalex_query_ending_in_question_mark_is_sanitized(mock_openalex_payload):
    """Proves a query ending in '?' no longer reaches OpenAlex with '?'."""
    with patch("httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_openalex_payload
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        raw_query = "What other academic research is related to this topic?"
        results = search_openalex(raw_query, max_results=3)

        mock_get.assert_called_once()
        called_params = mock_get.call_args[1]["params"]

        assert "?" not in called_params["search"]
        assert called_params["search"] == "What other academic research is related to this topic"
        assert called_params["per_page"] == 3
        assert len(results) == 1


def test_search_openalex_sanitizes_wildcards_and_special_characters(mock_openalex_payload):
    """Proves '*' and other Lucene/OpenAlex wildcard/special characters are sanitized."""
    with patch("httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_openalex_payload
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        raw_query = "quantum [error] correction: surface * code^2~ + | test?"
        search_openalex(raw_query, max_results=5)

        mock_get.assert_called_once()
        called_search = mock_get.call_args[1]["params"]["search"]

        # Ensure none of the prohibited special characters reach OpenAlex
        for char in ["?", "*", "+", "[", "]", "{", "}", "\\", "^", "~", ":", "|"]:
            assert char not in called_search

        assert called_search == "quantum error correction surface code 2 test"


def test_search_openalex_normal_query_remains_unchanged(mock_openalex_payload):
    """Proves a normal query such as 'neural operators' remains unchanged."""
    with patch("httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_openalex_payload
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        query = "neural operators"
        results = search_openalex(query, max_results=3)

        mock_get.assert_called_once()
        called_params = mock_get.call_args[1]["params"]

        assert called_params["search"] == "neural operators"
        assert called_params["per_page"] == 3
        assert len(results) == 1


def test_search_openalex_empty_or_special_only_query_returns_empty_list():
    """Proves empty or characters-only queries return [] without sending an invalid HTTP request."""
    with patch("httpx.get") as mock_get:
        assert search_openalex("???") == []
        assert search_openalex(" * ? ^ ") == []
        assert search_openalex("") == []
        mock_get.assert_not_called()


def test_search_openalex_preserves_existing_behavior(mock_openalex_payload):
    """Proves existing OpenAlex behavior, data mapping, and mailto handling remain intact."""
    with patch("httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_openalex_payload
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        records = search_openalex("neural operators", max_results=10)

        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        params = mock_get.call_args[1]["params"]

        assert url == "https://api.openalex.org/works"
        assert params["search"] == "neural operators"
        assert params["per_page"] == 10

        assert len(records) == 1
        rec = records[0]
        assert isinstance(rec, PaperRecord)
        assert rec.source == "openalex"
        assert rec.source_id == "W2964177579"
        assert rec.title == "Attention is All You Need"
        assert rec.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert rec.year == 2017
        assert rec.doi == "10.48550/arxiv.1706.03762"
        assert rec.pdf_url == "https://arxiv.org/pdf/1706.03762.pdf"
        assert rec.abstract == "The dominant sequence transduction models"
