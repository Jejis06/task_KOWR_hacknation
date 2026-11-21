"""Formy ochrony przyrody → ProtectedAreasInfo.

GDOŚ – Generalna Dyrekcja Ochrony Środowiska, GeoServer WFS `https://sdi.gdos.gov.pl/wfs`.
Dla każdej warstwy dwa zapytania (równolegle, bez geometrii w odpowiedzi):
  INTERSECTS(geom, <działka>)            → `hits` (działka leży w obszarze / dotyka go)
  DWITHIN(geom, <działka>, 1000, meters) → `nearby` (obszar w promieniu 1 km)
Pułapka: CQL na tym serwerze przyjmuje współrzędne EPSG:2180 w kolejności (N, E) – zamiana w `_wkt_ne`.
"""
from __future__ import annotations

import asyncio
from typing import Any

from shapely import transform as shp_transform
from shapely.geometry import shape

from app.connectors.base import Connector
from app.contracts.models import AnalysisContext, BlockStatus, DataBlock, ProtectedAreaHit, ProtectedAreasInfo
from app.core.geo import to_2180
from app.core.http import get_with_retry

GDOS_WFS = "https://sdi.gdos.gov.pl/wfs"
LIC = "Dane GDOŚ (Centralny Rejestr Form Ochrony Przyrody) – publiczne, bezpłatne, z podaniem źródła"
NEARBY_M = 1000

# typeName → (rodzaj dla rolnika, czy ma pole `kod`)
LAYERS: dict[str, tuple[str, bool]] = {
    "GDOS:ObszarySpecjalnejOchrony": ("Natura 2000 – obszar ptasi (OSO)", True),
    "GDOS:SpecjalneObszaryOchrony": ("Natura 2000 – obszar siedliskowy (SOO)", True),
    "GDOS:ParkiNarodowe": ("park narodowy", False),
    "GDOS:Rezerwaty": ("rezerwat przyrody", False),
    "GDOS:ParkiKrajobrazowe": ("park krajobrazowy", False),
    "GDOS:ObszaryChronionegoKrajobrazu": ("obszar chronionego krajobrazu", False),
    "GDOS:ZespolyPrzyrodniczoKrajobrazowe": ("zespół przyrodniczo-krajobrazowy", False),
    "GDOS:UzytkiEkologiczne": ("użytek ekologiczny", False),
    "GDOS:PomnikiPrzyrodyPowierzchniowe": ("pomnik przyrody (powierzchniowy)", False),
    "GDOS:ramsar": ("obszar Ramsar (mokradła)", False),
}


def _wkt_ne(geom_2180: Any, max_vertices: int = 150) -> str:
    g = geom_2180
    tol = 1.0
    while len(g.exterior.coords if hasattr(g, "exterior") else []) > max_vertices and tol < 50:
        g = geom_2180.simplify(tol)
        tol *= 2
    if g.geom_type != "Polygon":
        g = g.convex_hull
    swapped = shp_transform(g, lambda c: c[:, ::-1])
    return swapped.wkt.replace("POLYGON ", "POLYGON")


async def _query(type_name: str, has_code: bool, cql: str) -> list[dict]:
    r = await get_with_retry(GDOS_WFS, params={
        "SERVICE": "WFS", "VERSION": "1.1.0", "REQUEST": "GetFeature", "TYPENAME": type_name,
        "PROPERTYNAME": "nazwa,kod" if has_code else "nazwa", "OUTPUTFORMAT": "application/json",
        "CQL_FILTER": cql}, timeout_s=9)
    if "json" not in r.headers.get("content-type", ""):
        raise RuntimeError(f"GDOŚ WFS: {r.text[:200]}")
    return [f.get("properties", {}) for f in r.json().get("features", [])]


class ProtectedAreasConnector(Connector):
    key = "protected_areas"
    title = "Obszary chronione"
    category = "spatial"
    live_ttl_s = 30 * 24 * 3600
    timeout_s = 12
    cache_version = 2

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        parcel = to_2180(shape(ctx.parcel.geometry.model_dump()))
        wkt = _wkt_ne(parcel)
        tasks = []
        for tn, (_, has_code) in LAYERS.items():
            tasks.append(_query(tn, has_code, f"INTERSECTS(geom,{wkt})"))
            tasks.append(_query(tn, has_code, f"DWITHIN(geom,{wkt},{NEARBY_M},meters)"))
        res = await asyncio.gather(*tasks, return_exceptions=True)
        info = ProtectedAreasInfo()
        failed = []
        for i, (tn, (kind, _)) in enumerate(LAYERS.items()):
            inter, near = res[2 * i], res[2 * i + 1]
            if isinstance(inter, Exception):
                failed.append(kind)
                continue
            info.checked_layers.append(kind)
            names_in = set()
            for p in inter:
                info.hits.append(ProtectedAreaHit(kind=kind, name=p.get("nazwa"), code=p.get("kod"),
                                                  distance_m=0))
                names_in.add((p.get("nazwa"), p.get("kod")))
            if not isinstance(near, Exception):
                for p in near:
                    if (p.get("nazwa"), p.get("kod")) not in names_in:
                        info.nearby.append(ProtectedAreaHit(kind=kind, name=p.get("nazwa"), code=p.get("kod")))
        if not info.checked_layers:
            return self.block(BlockStatus.error, messages=[f"GDOŚ WFS niedostępny ({type(res[0]).__name__})."],
                              uncertainty=["Nie sprawdzono obszarów chronionych – źródło nie odpowiedziało."])
        # deduplikacja (ten sam obszar może przyjść kilkoma poligonami)
        info.hits = list({(h.kind, h.name, h.code): h for h in info.hits}.values())
        info.nearby = list({(h.kind, h.name, h.code): h for h in info.nearby}.values())
        unc = ["Granice form ochrony z rejestru GDOŚ; wiążące są akty prawne ustanawiające dany obszar.",
               f"„W pobliżu” = w promieniu {NEARBY_M} m od granic działki – może mieć znaczenie przy ocenie "
               "oddziaływania inwestycji (np. stawu, studni)."]
        msgs = [f"Nie sprawdzono warstw: {', '.join(failed)}."] if failed else []
        status = BlockStatus.partial if failed else BlockStatus.ok
        prov = self.prov("GDOŚ – Centralny Rejestr Form Ochrony Przyrody (WFS)", source_url="https://geoserwis.gdos.gov.pl/mapy/", licence=LIC,
                         notes=f"{len(info.checked_layers)} warstw; przecięcie z geometrią działki")
        return self.block(status, info, provenance=[prov], uncertainty=unc, messages=msgs)
