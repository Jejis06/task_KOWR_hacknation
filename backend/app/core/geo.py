"""Pomocnicze funkcje geometryczne (EPSG:4326 ↔ EPSG:2180 PUWG 1992)."""
from __future__ import annotations

from functools import lru_cache

from pyproj import Transformer
from shapely import wkt
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform


@lru_cache
def _tf(src: int, dst: int) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


def to_2180(geom: BaseGeometry) -> BaseGeometry:
    return transform(_tf(4326, 2180).transform, geom)


def to_4326(geom: BaseGeometry) -> BaseGeometry:
    return transform(_tf(2180, 4326).transform, geom)


def parse_wkt(text: str) -> BaseGeometry:
    if text.startswith("SRID="):
        text = text.split(";", 1)[1]
    return wkt.loads(text)


def area_ha(geom_4326: BaseGeometry) -> float:
    return to_2180(geom_4326).area / 10_000


def buffer_bbox_2180(geom_4326: BaseGeometry, buffer_m: float) -> tuple[float, float, float, float]:
    """BBOX w EPSG:2180 z buforem – do zapytań WCS/WMS (NMT, MPHP)."""
    return to_2180(geom_4326).buffer(buffer_m).bounds


def geom_to_geojson(geom: BaseGeometry) -> dict:
    return mapping(geom)


def geojson_to_geom(gj: dict) -> BaseGeometry:
    return shape(gj)
