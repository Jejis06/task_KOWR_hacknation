"""GUGiK ULDK – lokalizacja działki ewidencyjnej (po identyfikatorze lub po współrzędnych).

Dokumentacja: https://uldk.gugik.gov.pl/opis.html
Odpowiedź: linia 1 = status ("0" = OK, "-1 ..." = błąd), linia 2 = pola rozdzielone "|".
Licencja: dane publiczne PZGiK, bezpłatne (art. 40a ustawy Prawo geodezyjne i kartograficzne).

To NIE jest Connector bloku – to resolver wywoływany przed wszystkimi blokami (wynik = ParcelRef).
"""
from __future__ import annotations

import asyncio
import logging
import re

from app.contracts.models import GeoJSONGeometry, ParcelRef
from app.core.cache import cache_get, cache_set, make_key
from app.core.geo import area_ha, geom_to_geojson, parse_wkt
from app.core.http import get_client

log = logging.getLogger(__name__)

ULDK_URL = "https://uldk.gugik.gov.pl/"
RESULT_FIELDS = "geom_wkt,id,voivodeship,county,commune,region,parcel"
PARCEL_TTL_S = 7 * 24 * 3600

# 146505_8.0116.5   |  141201_1.0001.123/4   |  020101_1.0001.AR_1.12 (z arkuszem)
PARCEL_ID_RE = re.compile(r"^\d{6}_\d\.\d{4}(\.AR_\d+)?\.[\w/]+$")


class ParcelNotFound(Exception):
    pass


class UldkLimited(Exception):
    """GUGiK ogranicza zapytania z naszego IP (302 na integracja01…/resp/uldk.php albo 429) – to nie „brak działki”."""


async def _uldk_get(params: dict, attempts: int = 3) -> str:
    """ULDK bez podążania za przekierowaniem: przy limicie GUGiK odsyła 302 na stronę zastępczą, która zwraca „0” i
    fikcyjną geometrię (punkt z `inf`) – wcześniej kończyło się to błędem 500. Krótko ponawiamy, potem UldkLimited."""
    client = get_client()
    for i in range(attempts):
        try:
            r = await client.get(ULDK_URL, params=params, timeout=10, follow_redirects=False)
        except Exception as e:  # noqa: BLE001 – błąd sieci traktujemy jak niedostępność usługi
            log.warning("ULDK: %s", e)
            r = None
        if r is not None and r.status_code == 200:
            return r.text
        log.warning("ULDK ogranicza zapytania (HTTP %s, próba %d/%d)", r.status_code if r else "brak", i + 1, attempts)
        if i < attempts - 1:
            await asyncio.sleep(1.0 + i)
    raise UldkLimited("Usługa GUGiK ULDK chwilowo ogranicza liczbę zapytań – spróbuj ponownie za minutę.")


def looks_like_parcel_id(text: str) -> bool:
    return bool(PARCEL_ID_RE.match(text.strip()))


def _parse(body: str) -> ParcelRef:
    """Linia 1: GetParcelByXY → "0" = OK; GetParcelByIdOrNr → liczba wyników (≥1 = OK).
    Wartość ujemna („-1 brak wyników”) = błąd."""
    lines = [ln for ln in body.strip().splitlines() if ln.strip()]
    head = lines[0].strip() if lines else ""
    if not lines or head.startswith("-") or len(lines) < 2:
        raise ParcelNotFound(head or "pusta odpowiedź ULDK")
    # ULDK może zwrócić kilka działek (po nazwie obrębu) – bierzemy pierwszą
    f = lines[1].split("|")
    try:
        geom = parse_wkt(f[0])
    except Exception as e:  # noqa: BLE001 – uszkodzona geometria (np. strona zastępcza przy limicie)
        raise UldkLimited("GUGiK ULDK zwrócił niepoprawną geometrię – spróbuj ponownie za chwilę.") from e
    if geom.is_empty or not all(abs(v) < 1e6 for v in geom.bounds):
        raise UldkLimited("GUGiK ULDK zwrócił niepoprawną geometrię – spróbuj ponownie za chwilę.")
    pid = f[1]
    m = re.match(r"^(\d{6}_\d)\.(\d{4})(?:\.AR_\d+)?\.(.+)$", pid)
    minx, miny, maxx, maxy = geom.bounds
    c = geom.representative_point()
    return ParcelRef(
        id=pid,
        teryt_unit=m.group(1) if m else None,
        region_code=m.group(2) if m else None,
        parcel_number=m.group(3) if m else f[6] if len(f) > 6 else None,
        voivodeship=f[2] if len(f) > 2 else None,
        county=f[3] if len(f) > 3 else None,
        commune=f[4] if len(f) > 4 else None,
        region_name=f[5] if len(f) > 5 else None,
        geometry=GeoJSONGeometry(**geom_to_geojson(geom)),
        centroid=(round(c.x, 6), round(c.y, 6)),
        bbox=(minx, miny, maxx, maxy),
        area_ha=round(area_ha(geom), 4),
    )


async def resolve_by_id(parcel_id: str) -> ParcelRef:
    """Pełny identyfikator (np. 146505_8.0116.5) albo „nazwa_obrębu numer” – ULDK obsługuje oba."""
    key = make_key("uldk_id", id=parcel_id.strip())
    if (hit := cache_get(key)) is not None:
        return ParcelRef.model_validate(hit)
    ref = _parse(await _uldk_get({"request": "GetParcelByIdOrNr", "id": parcel_id.strip(),
                                  "result": RESULT_FIELDS, "srid": "4326"}))
    cache_set(key, ref.model_dump(mode="json"), PARCEL_TTL_S)
    return ref


async def resolve_by_xy(lon: float, lat: float) -> ParcelRef:
    key = make_key("uldk_xy", lon=round(lon, 6), lat=round(lat, 6))
    if (hit := cache_get(key)) is not None:
        return ParcelRef.model_validate(hit)
    ref = _parse(await _uldk_get({"request": "GetParcelByXY", "xy": f"{lon},{lat},4326",
                                  "result": RESULT_FIELDS, "srid": "4326"}))
    cache_set(key, ref.model_dump(mode="json"), PARCEL_TTL_S)
    cache_set(make_key("uldk_id", id=ref.id), ref.model_dump(mode="json"), PARCEL_TTL_S)
    return ref
