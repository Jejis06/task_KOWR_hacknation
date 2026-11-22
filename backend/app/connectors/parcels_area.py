"""Działki w obrysie narysowanym na mapie – z krajowego eksportu działek GUGiK (GeoParquet), bez ULDK.

Plik ma 4,6 GB, ale serwer obsługuje zapytania o fragment pliku (HTTP Range), a każda grupa wierszy ma statystyki
`geometry_bbox`. DuckDB czyta więc tylko grupy wierszy, których prostokąt przecina obrys (zwykle kilka–kilkanaście MB,
5–15 s). Wynik zapisujemy w cache, ten sam obrys nie pyta źródła drugi raz.
Licencja: dane PZGiK, bezpłatne (art. 40a ustawy Prawo geodezyjne i kartograficzne).
"""
from __future__ import annotations

import asyncio
import logging
import threading

from shapely import wkb
from shapely.geometry import Polygon, mapping

from app.contracts.models import GeoJSONGeometry, ParcelRef
from app.core.cache import cache_get, cache_set, make_key
from app.core.geo import to_2180, to_4326

log = logging.getLogger(__name__)

PARQUET_URL = "https://opendata.geoportal.gov.pl/InneDane/latest_exports/eziudp_wfs/PARQUET/0_dzialki.parquet"
TTL_S = 30 * 24 * 3600
MAX_AREA_HA = 400          # większy obrys = setki działek i długie czytanie pliku
MAX_PARCELS = 25
_lock = threading.Lock()   # jedno połączenie DuckDB na proces (zapytania po kolei)
_con = None


class AreaTooLarge(Exception):
    pass


def _connection():
    global _con
    if _con is None:
        import duckdb
        _con = duckdb.connect()
        _con.execute("INSTALL httpfs; LOAD httpfs; SET enable_http_metadata_cache = true; SET enable_progress_bar = false;")
    return _con


def _query(bounds: tuple[float, float, float, float]) -> list[tuple]:
    minx, miny, maxx, maxy = bounds
    with _lock:
        return _connection().execute(
            f"""SELECT id_dzialki, numer_dzialki, nazwa_obrebu, numer_jednostki, nazwa_gminy, geometry
                FROM read_parquet('{PARQUET_URL}')
                WHERE geometry_bbox.xmax >= ? AND geometry_bbox.xmin <= ?
                  AND geometry_bbox.ymax >= ? AND geometry_bbox.ymin <= ?""",
            [minx, maxx, miny, maxy]).fetchall()


async def parcels_in_polygon(ring_lonlat: list[tuple[float, float]]) -> tuple[list[ParcelRef], int]:
    """Działki przecinane przez krawędź obrysu albo leżące w jego środku (EPSG:4326 na wejściu i wyjściu).
    Zwraca (do 25 największych działek, liczba wszystkich działek w obrysie)."""
    poly4326 = Polygon(ring_lonlat)
    if not poly4326.is_valid:
        poly4326 = poly4326.buffer(0)
    poly = to_2180(poly4326)
    if poly.area / 10_000 > MAX_AREA_HA:
        raise AreaTooLarge(f"Obrys jest za duży (maks. {MAX_AREA_HA} ha) – zaznacz mniejszy obszar.")
    key = make_key("parcels_area", wkt=poly.simplify(1).wkt)
    if (hit := cache_get(key)) is not None:
        return [ParcelRef.model_validate(x) for x in hit["parcels"]], hit["total"]
    rows = await asyncio.to_thread(_query, poly.bounds)
    out: list[ParcelRef] = []
    for pid, num, obreb, _unit, gmina, geom_wkb in rows:
        g = wkb.loads(bytes(geom_wkb))
        if not g.intersects(poly):
            continue
        g4326 = to_4326(g)
        minx, miny, maxx, maxy = g4326.bounds
        c = g4326.representative_point()
        out.append(ParcelRef(id=pid, parcel_number=num, region_name=obreb, commune=gmina,
                             teryt_unit=pid.split(".")[0] if "." in pid else None,
                             geometry=GeoJSONGeometry(**mapping(g4326)), centroid=(round(c.x, 6), round(c.y, 6)),
                             bbox=(minx, miny, maxx, maxy), area_ha=round(g.area / 10_000, 4)))
    out.sort(key=lambda p: -p.area_ha)
    total = len(out)
    out = out[:MAX_PARCELS]
    cache_set(key, {"parcels": [p.model_dump(mode="json") for p in out], "total": total}, TTL_S)
    # każda działka z obrysu trafia też do cache ULDK – późniejsza analiza nie pyta ULDK
    for p in out:
        cache_set(make_key("uldk_id", id=p.id), p.model_dump(mode="json"), 7 * 24 * 3600)
    return out, total
