"""
Tests for the SSRF guard (new-plan.md section 58): the fetch/crawl entry
point that untrusted URLs (from the LLM or the user) must pass through.
"""
from __future__ import annotations

import pytest

from prometheus.providers.web.security import UnsafeURLError, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://0.0.0.0/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
    ],
)
def test_validate_public_url_rejects_internal_addresses(url):
    with pytest.raises(UnsafeURLError):
        validate_public_url(url)


def test_validate_public_url_rejects_non_http_scheme():
    with pytest.raises(UnsafeURLError):
        validate_public_url("file:///etc/passwd")


def test_validate_public_url_rejects_missing_host():
    with pytest.raises(UnsafeURLError):
        validate_public_url("http:///path")


def test_validate_public_url_accepts_public_host():
    # example.com resolves to a public IP; requires network access in CI,
    # but exercises the real resolution path rather than mocking it away.
    validate_public_url("https://example.com/")
