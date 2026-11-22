"""Wyszukiwanie adresu → punkt na mapie (i działka pod nim, gdy adres ma numer domu).

Kolejność: usługa adresowa GUGiK (UUG, bez klucza) z krótkim limitem czasu; gdy nie odpowiada albo ogranicza
zapytania – Nominatim (OpenStreetMap; zasady: maks. 1 zapytanie/s, identyfikacja klienta, cache wyników).
Wyniki trzymamy w cache 30 dni – ten sam adres nie pyta źródeł drugi raz.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.cache import cache_get, cache_set, make_key
from app.core.geo import to_4326
from app.core.http import RateLimited, get_with_retry

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/geocode", tags=["geocode"])

UUG_URL = "https://services.gugik.gov.pl/uug/"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
TTL_S = 30 * 24 * 3600
_nominatim_lock = asyncio.Lock()
_nominatim_last = 0.0


class GeocodeResult(BaseModel):
    label: str
    lon: float
    lat: float
    has_house_number: bool           # adres z numerem → zaznaczamy działkę pod punktem; bez numeru → tylko przybliżenie
    source: str


def _has_number(q: str) -> bool:
    return bool(re.search(r"\d+[a-zA-Z]?(\s*/\s*\d+)?\s*$", q.strip()))


async def _uug(q: str) -> GeocodeResult | None:
    from shapely.geometry import Point
    try:
        r = await get_with_retry(UUG_URL, params={"request": "GetAddress", "address": q}, timeout_s=4, attempts=1)
        j = r.json()
    except (RateLimited, Exception) as e:  # noqa: BLE001 – każdy błąd GUGiK = przechodzimy na zapas
        log.info("UUG niedostępne: %s", e)
        return None
    res = (j or {}).get("results") or {}
    first = next(iter(res.values()), None) if isinstance(res, dict) else (res[0] if res else None)
    if not first or first.get("x") is None:
        return None
    # UUG zwraca współrzędne w EPSG:2180 (x = wschód, y = północ)
    p = to_4326(Point(float(first["x"]), float(first["y"])))
    label = ", ".join(str(first[k]) for k in ("city", "street", "number") if first.get(k))
    return GeocodeResult(label=label or q, lon=round(p.x, 6), lat=round(p.y, 6),
                         has_house_number=bool(first.get("number")), source="GUGiK – usługa adresowa (UUG)")


async def _nominatim(q: str) -> GeocodeResult | None:
    global _nominatim_last
    async with _nominatim_lock:                     # zasady Nominatim: nie częściej niż 1 zapytanie na sekundę
        wait = 1.05 - (time.monotonic() - _nominatim_last)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            r = await get_with_retry(NOMINATIM_URL, params={"q": q, "format": "jsonv2", "countrycodes": "pl", "limit": 1,
                                                            "addressdetails": 1}, timeout_s=6, attempts=1)
            j = r.json()
        except Exception as e:  # noqa: BLE001
            log.info("Nominatim niedostępny: %s", e)
            return None
        finally:
            _nominatim_last = time.monotonic()
    if not j:
        return None
    hit = j[0]
    return GeocodeResult(label=hit.get("display_name", q), lon=float(hit["lon"]), lat=float(hit["lat"]),
                         has_house_number=bool((hit.get("address") or {}).get("house_number")) or _has_number(q),
                         source="OpenStreetMap Nominatim (© współtwórcy OpenStreetMap, ODbL)")


@router.get("", response_model=GeocodeResult)
async def geocode(q: str = Query(..., min_length=3, max_length=200)) -> GeocodeResult:
    key = make_key("geocode", q=q.strip().lower())
    if (hit := cache_get(key)) is not None:
        return GeocodeResult.model_validate(hit)
    res = await _uug(q) or await _nominatim(q)
    if res is None:
        raise HTTPException(404, "Nie znaleziono adresu. Sprawdź pisownię albo wpisz miejscowość i ulicę.")
    cache_set(key, res.model_dump(), TTL_S)
    return res
