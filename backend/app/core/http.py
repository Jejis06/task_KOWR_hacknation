"""Wspólny klient HTTP (async) – jeden na proces, z retry i limitami połączeń.

Wszystkie konektory MUSZĄ używać `get_client()` zamiast tworzyć własne klienty.
"""
from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlsplit

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


# ── limity źródeł (głównie GUGiK) ──
# GUGiK przy limicie z jednego IP odsyła 302 na stronę zastępczą integracja01…/resp/<usługa>.php (nie 429). Taką
# odpowiedź traktujemy jak limit: rzucamy RateLimited i przez COOLDOWN_S nie pytamy tego hosta wcale – szybki fallback
# w konektorach zamiast kolejnych zapytań, które tylko przedłużają blokadę.
COOLDOWN_S = 90
_cooldown_until: dict[str, float] = {}


def _host(url: str) -> str:
    return urlsplit(str(url)).netloc


def is_limited(url: str) -> bool:
    return time.monotonic() < _cooldown_until.get(_host(url), 0.0)


def mark_limited(url: str, seconds: float = COOLDOWN_S) -> None:
    _cooldown_until[_host(url)] = time.monotonic() + seconds
    log.warning("Źródło %s ogranicza zapytania – przerwa %.0f s", _host(url), seconds)


def is_limit_response(r: httpx.Response) -> bool:
    """429 albo przekierowanie GUGiK na stronę zastępczą (/resp/…)."""
    if r.status_code == 429:
        return True
    hops = [*r.history, r] if r.history else [r]
    for h in hops:
        loc = h.headers.get("location", "") if h.is_redirect else ""
        if "/resp/" in loc or "/resp/" in urlsplit(str(h.url)).path:
            return True
    return False


async def get_with_retry(url: str, *, params: dict | None = None, attempts: int = 2,
                         backoff_s: float = 0.6, timeout_s: float | None = None) -> httpx.Response:
    """GET z ponowieniem na 5xx. 429 → RateLimited (bez ponawiania, od razu fallback)."""
    client = get_client()
    if is_limited(url):
        raise RateLimited(f"{_host(url)}: przerwa po limicie")
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            r = await client.get(url, params=params, timeout=timeout_s or client.timeout)
            if is_limit_response(r):
                mark_limited(url)
                raise RateLimited(f"limit from {url}")
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


async def post_with_retry(url: str, *, data: dict | None = None, attempts: int = 2, backoff_s: float = 0.6,
                          timeout_s: float | None = None) -> httpx.Response:
    """POST (formularz) z ponowieniem na 5xx/błędy transportu. 429 → RateLimited."""
    client = get_client()
    if is_limited(url):
        raise RateLimited(f"{_host(url)}: przerwa po limicie")
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            r = await client.post(url, data=data, timeout=timeout_s or client.timeout)
            if is_limit_response(r):
                mark_limited(url)
                raise RateLimited(f"limit from {url}")
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
