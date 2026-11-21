"""Wspólny klient HTTP (async) – jeden na proces, z retry i limitami połączeń.

Wszystkie konektory MUSZĄ używać `get_client()` zamiast tworzyć własne klienty.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent},
            timeout=httpx.Timeout(settings.default_connector_timeout_s, connect=settings.http_connect_timeout_s),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            transport=httpx.AsyncHTTPTransport(retries=2),  # retry na błędy połączenia
            follow_redirects=True,
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class RateLimited(Exception):
    """Źródło zwróciło 429 – konektor powinien przełączyć się na fallback."""


async def get_with_retry(url: str, *, params: dict | None = None, attempts: int = 2,
                         backoff_s: float = 0.6, timeout_s: float | None = None) -> httpx.Response:
    """GET z ponowieniem na 5xx. 429 → RateLimited (bez ponawiania, od razu fallback)."""
    client = get_client()
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            r = await client.get(url, params=params, timeout=timeout_s or client.timeout)
            if r.status_code == 429:
                raise RateLimited(f"429 from {url}")
            if r.status_code >= 500:
                raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
            r.raise_for_status()
            return r
        except RateLimited:
            raise
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last_exc = e
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500:
                raise
            if i < attempts - 1:
                await asyncio.sleep(backoff_s * (2**i))
    assert last_exc is not None
    raise last_exc
