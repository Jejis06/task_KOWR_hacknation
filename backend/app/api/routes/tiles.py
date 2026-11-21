"""Proxy kafelków mapy z cache na dysku – mniej zapytań do GUGiK/OSM i odporność na ich limity.

Każdy kafelek pobieramy z serwera źródłowego raz, potem serwujemy z cache (diskcache, 30 dni) z nagłówkiem
Cache-Control, więc przeglądarka też go zapamiętuje. Kafelki WMS (ortofotomapa, granice działek) składamy
z adresu z/x/y: bbox w EPSG:3857 i obraz 512×512 px (Leaflet: tileSize 512, zoomOffset −1).
Upstream ograniczamy semaforem (kilka równoległych zapytań na źródło), żeby nie wywoływać limitów GUGiK.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time

from fastapi import APIRouter, HTTPException, Response

from app.core.cache import cache_get, cache_set, make_key
from app.core.http import get_client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tiles", tags=["tiles"])

TILE_TTL_S = 30 * 24 * 3600
BROWSER_MAX_AGE_S = 7 * 24 * 3600
ORIGIN_SHIFT = 2 * math.pi * 6378137 / 2.0   # połowa obwodu Ziemi w EPSG:3857 [m]

LAYERS: dict[str, dict] = {
    "ortho": {
        "kind": "wms", "url": "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution",
        "params": {"LAYERS": "Raster", "FORMAT": "image/jpeg", "TRANSPARENT": "FALSE"}, "media": "image/jpeg",
        "size": 512, "max_z": 19, "limit": 4,
    },
    "parcels": {
        "kind": "wms", "url": "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow",
        "params": {"LAYERS": "dzialki,numery_dzialek", "FORMAT": "image/png", "TRANSPARENT": "TRUE"},
        "media": "image/png", "size": 512, "max_z": 19, "limit": 3,
    },
    "osm": {
        "kind": "xyz", "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "media": "image/png",
        "size": 256, "max_z": 19, "limit": 2,
    },
}
_SEMS: dict[str, asyncio.Semaphore] = {}
_COOLDOWN_UNTIL: dict[str, float] = {}   # po limicie źródła (302/429) przez chwilę nie pytamy go wcale
COOLDOWN_S = 60


def tile_bbox_3857(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Granice kafelka XYZ (schemat Google/OSM, oś Y w dół) w metrach EPSG:3857."""
    n = 2 ** z
    size = 2 * ORIGIN_SHIFT / n
    minx = -ORIGIN_SHIFT + x * size
    maxy = ORIGIN_SHIFT - y * size
    return minx, maxy - size, minx + size, maxy


async def _fetch(layer: str, z: int, x: int, y: int) -> bytes:
    cfg = LAYERS[layer]
    if cfg["kind"] == "wms":
        minx, miny, maxx, maxy = tile_bbox_3857(z, x, y)
        params = {"SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "CRS": "EPSG:3857", "STYLES": "",
                  "WIDTH": cfg["size"], "HEIGHT": cfg["size"], "BBOX": f"{minx},{miny},{maxx},{maxy}", **cfg["params"]}
        url = cfg["url"]
    else:
        params = None
        url = cfg["url"].format(z=z, x=x, y=y)
    if time.monotonic() < _COOLDOWN_UNTIL.get(layer, 0):
        raise HTTPException(503, f"Źródło kafelków {layer} chwilowo ogranicza zapytania.", headers={"Retry-After": str(COOLDOWN_S)})
    sem = _SEMS.setdefault(layer, asyncio.Semaphore(cfg["limit"]))
    async with sem:
        # bez podążania za przekierowaniem: GUGiK przy limicie odsyła 302 na stronę zastępczą (nie obraz)
        r = await get_client().get(url, params=params, timeout=15, follow_redirects=False)
    if r.status_code in (301, 302, 303, 307, 429):
        _COOLDOWN_UNTIL[layer] = time.monotonic() + COOLDOWN_S
        log.warning("Kafelki %s: źródło ogranicza zapytania (HTTP %s) – przerwa %d s", layer, r.status_code, COOLDOWN_S)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise HTTPException(502, f"Źródło kafelków {layer} niedostępne (HTTP {r.status_code}).")
    return r.content


@router.get("/{layer}/{z}/{x}/{y}")
async def tile(layer: str, z: int, x: int, y: int) -> Response:
    cfg = LAYERS.get(layer)
    if cfg is None:
        raise HTTPException(404, "Nieznana warstwa mapy.")
    if not (0 <= z <= cfg["max_z"]) or not (0 <= x < 2 ** z) or not (0 <= y < 2 ** z):
        raise HTTPException(404, "Kafelek poza zakresem.")
    key = make_key("tile", layer=layer, z=z, x=x, y=y)
    data = cache_get(key)
    hit = data is not None
    if not hit:
        data = await _fetch(layer, z, x, y)
        cache_set(key, data, TILE_TTL_S)
    return Response(content=data, media_type=cfg["media"],
                    headers={"Cache-Control": f"public, max-age={BROWSER_MAX_AGE_S}", "X-Tile-Cache": "hit" if hit else "miss"})
