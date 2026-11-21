"""Pokrycie terenu w granicach działki → LandCoverInfo (działka ≠ pole!).

1) ESA WorldCover 10 m (v200, 2021, CC BY 4.0) – Microsoft Planetary Computer, Data API
   `item/statistics?categorical=true` dla geometrii działki → histogram klas (liczony na serwerze).
2) BDOT10k (PZGiK, kopia w ArcGIS REST PIG-PIB) – pokrycie terenu 1:10 000: poligony przecinające działkę,
   udział = pole przecięcia / pole działki (dokładniejsze granice niż piksel 10 m, aktualność ~2012–2015).
"""
from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

from shapely.geometry import shape

from app.connectors.base import Connector
from app.connectors.hydrology import BDOT, arcgis_query, esri_geom
from app.contracts.models import AnalysisContext, BlockStatus, DataBlock, LandCoverInfo
from app.core.geo import to_2180
from app.core.http import get_client

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_STATS = "https://planetarycomputer.microsoft.com/api/data/v1/item/statistics"
WC_CLASSES = {10: "las i zadrzewienia", 20: "zarośla", 30: "łąki i pastwiska (roślinność trawiasta)",
              40: "grunty orne", 50: "zabudowa", 60: "teren bez roślinności", 70: "śnieg i lód", 80: "wody",
              90: "mokradła", 95: "namorzyny", 100: "mchy i porosty"}
BDOT_LC = {47: "las i zadrzewienia", 46: "zarośla", 49: "uprawy rolne lub roślinność trawiasta",
           48: "uprawy trwałe (sady, plantacje)", 50: "zabudowa", 51: "teren przemysłowy", 30: "wody",
           45: "mokradła", 44: "szuwary", 52: "pozostały teren niezabudowany", 28: "grunty nieużytkowane",
           29: "zwałowiska i wyrobiska", 53: "plac"}
AGRI_WC = (30, 40)
AGRI_BDOT = ("uprawy rolne lub roślinność trawiasta", "uprawy trwałe (sady, plantacje)")
LIC_WC = "CC BY 4.0 – © ESA WorldCover project 2021 / Copernicus Sentinel data (via Microsoft Planetary Computer)"
LIC_BDOT = "BDOT10k (PZGiK) – bezpłatne; kopia udostępniana przez PIG-PIB"


async def worldcover_hist(geometry: dict, bbox: tuple[float, float, float, float]) -> Counter:
    client = get_client()
    r = await client.post(PC_STAC, json={"collections": ["esa-worldcover"], "bbox": list(bbox), "limit": 10},
                          timeout=10)
    r.raise_for_status()
    items = [f for f in r.json().get("features", []) if "v200" in f["id"]] or r.json().get("features", [])
    if not items:
        raise RuntimeError("WorldCover: brak kafla dla działki")
    feature = {"type": "Feature", "properties": {}, "geometry": geometry}

    async def one(item_id: str) -> Counter:
        rr = await client.post(PC_STATS, params={"collection": "esa-worldcover", "item": item_id, "assets": "map",
                                                 "categorical": "true", "max_size": "1024"}, json=feature, timeout=12)
        rr.raise_for_status()
        st = next(iter(rr.json()["properties"]["statistics"].values()))
        counts, classes = st["histogram"]
        return Counter({int(c): int(n) for n, c in zip(counts, classes)})

    total: Counter = Counter()
    for c in await asyncio.gather(*(one(it["id"]) for it in items[:4]), return_exceptions=True):
        if isinstance(c, Counter):
            total += c
    if not total:
        raise RuntimeError("WorldCover: brak pikseli w granicach działki")
    return total


async def bdot_shares(parcel_2180: Any) -> dict[str, float]:
    env = parcel_2180.bounds
    res = await asyncio.gather(*(arcgis_query(f"{BDOT}/{lid}", env, offset=1.0) for lid in BDOT_LC),
                               return_exceptions=True)
    if all(isinstance(r, Exception) for r in res):
        raise RuntimeError("BDOT10k niedostępne")
    area = parcel_2180.area
    acc: Counter = Counter()
    for lid, fs in zip(BDOT_LC, res):
        if isinstance(fs, Exception):
            continue
        for f in fs:
            g = esri_geom(f.get("geometry"))
            if g is None or g.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            inter = g.buffer(0).intersection(parcel_2180).area
            if inter > 0:
                acc[BDOT_LC[lid]] += inter
    return {k: round(100 * v / area, 1) for k, v in acc.most_common() if v / area >= 0.005}


class LandCoverConnector(Connector):
    key = "land_cover"
    title = "Użytkowanie terenu"
    category = "spatial"
    live_ttl_s = 30 * 24 * 3600
    timeout_s = 12
    cache_version = 2

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        geom = ctx.parcel.geometry.model_dump()
        parcel_2180 = to_2180(shape(geom))
        wc, bd = await asyncio.gather(worldcover_hist(geom, ctx.parcel.bbox), bdot_shares(parcel_2180),
                                      return_exceptions=True)
        info = LandCoverInfo()
        provs, msgs, unc = [], [], []
        if isinstance(wc, Exception):
            msgs.append(f"ESA WorldCover niedostępny: {type(wc).__name__}.")
        else:
            tot = sum(wc.values())
            info.classes = {WC_CLASSES.get(k, str(k)): round(100 * v / tot, 1) for k, v in wc.most_common()}
            info.agricultural_share_pct = round(100 * sum(wc[k] for k in AGRI_WC) / tot, 1)
            info.cropland_share_pct = round(100 * wc[40] / tot, 1)
            info.source_used = "esa_worldcover_2021"
            provs.append(self.prov("ESA WorldCover 10 m v200 (2021)", source_url=PC_STATS, licence=LIC_WC,
                                   notes=f"{tot} pikseli 10 m w granicach działki"))
            unc.append("ESA WorldCover to mapa z 2021 r. (klasyfikacja satelitarna, dokładność ok. 75–80%) – "
                       "obecne użytkowanie mogło się zmienić.")
        if isinstance(bd, Exception):
            msgs.append(f"BDOT10k niedostępny: {type(bd).__name__}.")
        elif sum(bd.values()) < 80:
            msgs.append("BDOT10k (kopia PIG-PIB) nie pokrywa tej działki w całości – pominięto (dane niekompletne).")
        else:
            info.bdot_classes = bd
            if bd:
                provs.append(self.prov("BDOT10k – pokrycie terenu (kopia w usłudze PIG-PIB)", source_url=BDOT,
                                       licence=LIC_BDOT, notes="udział = pole przecięcia z działką"))
                unc.append("BDOT10k: aktualność danych głównie 2012–2015; klasa „uprawy rolne lub roślinność "
                           "trawiasta” nie rozróżnia gruntu ornego od łąki.")
                if info.agricultural_share_pct is None:
                    info.agricultural_share_pct = round(sum(v for k, v in bd.items() if k in AGRI_BDOT), 1)
                    info.source_used = "bdot10k"
        if not provs:
            return self.block(BlockStatus.error, messages=msgs,
                              uncertainty=["Nie ustalono użytkowania terenu – źródła nie odpowiedziały."])
        if info.agricultural_share_pct is not None and info.agricultural_share_pct < 50:
            unc.append(f"Tylko ok. {info.agricultural_share_pct:.0f}% działki to grunty rolne (orne lub łąki) – "
                       "wskaźniki satelitarne i ocena wodna dotyczą głównie tej części.")
        status = BlockStatus.ok if info.source_used else BlockStatus.partial
        return self.block(status, info, provenance=provs, uncertainty=unc, messages=msgs)
