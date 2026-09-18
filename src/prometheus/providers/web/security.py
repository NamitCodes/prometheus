"""SSRF guard for web fetch/crawl (new-plan.md section 58).

Fetching a URL the user (or the LLM) supplies is untrusted-input territory --
without this, an agent could be steered into hitting internal services,
localhost, or a cloud metadata endpoint. Every fetch, including each hop of
a redirect chain, must go through `validate_public_url` first.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(ValueError):
    """Raised when a URL is disallowed (bad scheme, or resolves to a non-public address)."""


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"unsupported URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise UnsafeURLError(f"URL has no hostname: {url!r}")

    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"could not resolve host {parsed.hostname!r}: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local  # covers the 169.254.169.254 cloud metadata endpoint
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeURLError(f"{url!r} resolves to a non-public address ({ip}); refusing to fetch")
