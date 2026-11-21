"""Pomocnicze zapytania OGC (WMS GetFeatureInfo, WFS) – wspólne dla konektorów.

Kolejność osi: WMS 1.3.0 + EPSG:2180 → BBOX = (northing_min, easting_min, northing_max, easting_max).
`pyproj` z `always_xy=True` daje (easting, northing) – zamiana robi `point_bbox_2180`.
Sprawdzone na znanym punkcie (Środa Wlkp.: E=380606, N=482882 → kontur gleby czarnej ziemi, kompleks 1).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app.core.http import get_with_retry


def point_bbox_2180(e: float, n: float, half_m: float = 50.0, axis_ne: bool = True) -> str:
    if axis_ne:
        return f"{n - half_m},{e - half_m},{n + half_m},{e + half_m}"
    return f"{e - half_m},{n - half_m},{e + half_m},{n + half_m}"


async def wms_feature_info(url: str, layers: str, e: float, n: float, *, info_format: str = "text/xml",
                           version: str = "1.3.0", half_m: float = 50.0, timeout_s: float = 8,
                           feature_count: int = 10, extra: dict | None = None) -> str:
    """GetFeatureInfo w punkcie (EPSG:2180). Zwraca surowe body (format zależy od serwera)."""
    params: dict[str, Any] = {
        "SERVICE": "WMS", "VERSION": version, "REQUEST": "GetFeatureInfo", "LAYERS": layers,
        "QUERY_LAYERS": layers, "STYLES": "", "WIDTH": 101, "HEIGHT": 101, "INFO_FORMAT": info_format,
        "FEATURE_COUNT": feature_count, "FORMAT": "image/png",
    }
    if version == "1.3.0":
        params.update(CRS="EPSG:2180", BBOX=point_bbox_2180(e, n, half_m, axis_ne=True), I=50, J=50)
    else:
        params.update(SRS="EPSG:2180", BBOX=point_bbox_2180(e, n, half_m, axis_ne=False), X=50, Y=50)
    if extra:
        params.update(extra)
    r = await get_with_retry(url, params=params, timeout_s=timeout_s)
    return r.text


def esri_xml_fields(body: str) -> list[dict[str, str]]:
    """ArcGIS Server WMS `text/xml`: <FIELDS a="..." b="..."/> → lista słowników (bez wartości "Null")."""
    if "ServiceException" in body:
        raise ValueError(f"WMS exception: {body[:300]}")
    root = ET.fromstring(body.encode() if isinstance(body, str) else body)
    out = []
    for el in root.iter():
        if el.tag.endswith("FIELDS"):
            out.append({k: v for k, v in el.attrib.items() if v not in ("Null", "", None)})
    return out
