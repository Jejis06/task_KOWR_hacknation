"""Cache dyskowy (diskcache/SQLite) – przeżywa restart serwera.

Polityka TTL (patrz AGENTS.md §5):
- dane historyczne (as_of starsze niż 7 dni) są niezmienne → długi TTL (30 dni);
- dane bieżące (as_of ≈ dziś) → krótki TTL ustawiany przez konektor (np. 3 h dla meteo).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Any

import diskcache

from app.config import settings

_cache: diskcache.Cache | None = None
HISTORICAL_TTL_S = 30 * 24 * 3600


def get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        _cache = diskcache.Cache(str(settings.cache_dir), size_limit=2 * 1024**3)
    return _cache


def make_key(namespace: str, **parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return f"{namespace}:{hashlib.sha1(raw.encode()).hexdigest()}"


def ttl_for(as_of: date, live_ttl_s: int) -> int:
    return HISTORICAL_TTL_S if as_of < date.today() - timedelta(days=7) else live_ttl_s


def cache_get(key: str) -> Any | None:
    return get_cache().get(key)


def cache_set(key: str, value: Any, ttl_s: int) -> None:
    get_cache().set(key, value, expire=ttl_s)
