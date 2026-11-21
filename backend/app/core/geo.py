"""Pomocnicze funkcje geometryczne (EPSG:4326 ↔ EPSG:2180 PUWG 1992)."""
from __future__ import annotations

from functools import lru_cache

from pyproj import Transformer
from shapely import wkt
from shapely.geometry import Point, mapping, shape
from shapely.geometry.base import BaseGeometry
import numpy as np
import shapely


@lru_cache
def _tf(src: int, dst: int) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


def _reproject(geom: BaseGeometry, src: int, dst: int) -> BaseGeometry:
    tf = _tf(src, dst)
    return shapely.transform(geom, lambda c: np.column_stack(tf.transform(c[:, 0], c[:, 1])))


def to_2180(geom: BaseGeometry) -> BaseGeometry:
    return _reproject(geom, 4326, 2180)


def to_4326(geom: BaseGeometry) -> BaseGeometry:
    return _reproject(geom, 2180, 4326)


def parse_wkt(text: str) -> BaseGeometry:
    if text.startswith("SRID="):
        text = text.split(";", 1)[1]
    return wkt.loads(text)


def area_ha(geom_4326: BaseGeometry) -> float:
    return to_2180(geom_4326).area / 10_000


def buffer_bbox_2180(geom_4326: BaseGeometry, buffer_m: float) -> tuple[float, float, float, float]:
    """BBOX w EPSG:2180 z buforem – do zapytań WCS/WMS (NMT, MPHP)."""
    return to_2180(geom_4326).buffer(buffer_m).bounds


def sample_points_2180(geom_4326: BaseGeometry, n: int = 5, inset_m: float = 8.0) -> list[tuple[float, float]]:
    """Do `n` punktów (E, N w EPSG:2180) rozłożonych WEWNĄTRZ działki: punkt reprezentatywny + siatka.
    Odsunięcie od granicy (`inset_m`) zmniejsza ryzyko trafienia w sąsiedni kontur/drogę."""
    g = to_2180(geom_4326)
    inner = g.buffer(-inset_m)
    if inner.is_empty or inner.area < g.area * 0.2:
        inner = g
    rp = inner.representative_point()
    pts = [(rp.x, rp.y)]
    if n <= 1:
        return pts
    minx, miny, maxx, maxy = inner.bounds
    k = 7
    cand = []
    for i in range(k):
        for j in range(k):
            x = minx + (i + 0.5) * (maxx - minx) / k
            y = miny + (j + 0.5) * (maxy - miny) / k
            if inner.contains(Point(x, y)):
                cand.append((x, y))
    # wybór najbardziej rozproszonych (farthest-point sampling)
    while cand and len(pts) < n:
        best = max(cand, key=lambda c: min((c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2 for p in pts))
        if min((best[0] - p[0]) ** 2 + (best[1] - p[1]) ** 2 for p in pts) < 25:  # < 5 m – bez sensu
            break
        pts.append(best)
        cand.remove(best)
    return pts


def geom_to_geojson(geom: BaseGeometry) -> dict:
    return mapping(geom)


def geojson_to_geom(gj: dict) -> BaseGeometry:
    return shape(gj)
