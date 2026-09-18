import dataclasses

import pytest

import prometheus.retrieval.hybrid_search as hybrid_search_module
import prometheus.retrieval.vector_store as vector_store_module


@pytest.fixture(autouse=True)
def _isolated_embedded_chroma(tmp_path, monkeypatch):
    """Tests always use embedded Chroma in a temp dir, regardless of .env
    (CHROMA_SERVER_URL) -- individual tests may still override further."""
    isolated = dataclasses.replace(
        vector_store_module.settings,
        chroma_server_url="",
        chroma_persist_dir=str(tmp_path / "chroma_default"),
    )
    monkeypatch.setattr(vector_store_module, "settings", isolated)
    monkeypatch.setattr(hybrid_search_module, "settings", isolated)
    monkeypatch.setattr(vector_store_module, "_vector_store", None)
