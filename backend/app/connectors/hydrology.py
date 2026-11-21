"""Hydrologia → HydrologyInfo.

Źródła (wszystkie bez klucza, zapytania równoległe):
- ISOK / PGW Wody Polskie – mapy zagrożenia powodziowego (MZP), INSPIRE WMS warstwa `NZ.Fluvial`.
  GetFeatureInfo na tej usłudze trwa 3–10 s (ciężkie poligony), więc najpierw GetMap PNG działki (≈0,3 s)
  → jeśli jakikolwiek piksel strefy leży w działce, jedno GetFeatureInfo w tym pikselu podaje scenariusze.
- BDOT10k (kopia w ArcGIS REST PIG-PIB `mapa_topo/bdot_10k`): cieki, cieki okresowe, rowy melioracyjne,
  kanały, wody powierzchniowe w promieniu 1 km. MPHP Wód Polskich zwraca 401 (21.11.2026).
- PIG-PIB CBDH (`hydrogeologia/cbdh_otwory`): najbliższe otwory hydrogeologiczne (głębokość, rok, typ).
- PIG-PIB GZWP (`hydrogeologia/gzwp`), JCWPd 2022–2027 (`hydrogeologia/jcwpd`, region wodny),
  obszary zagrożone podtopieniami (`hydrogeologia/podtopienia`).
- MHP (głębokość do 1. poziomu wodonośnego) – usługa PIG wymaga tokena → brak, komunikat wprost.
"""
from __future__ import annotations

import asyncio
from typing import Any

from shapely.geometry import LineString, Point, Polygon, mapping, shape

from app.connectors.base import Connector
from app.contracts.models import (
    AnalysisContext,
    BlockStatus,
    DataBlock,
    GeoJSONGeometry,
    HydrologyInfo,
    WaterFeature,
)
from app.core.geo import to_2180, to_4326
from app.core.http import get_with_retry

ISOK_WMS = "https://wody.isok.gov.pl/wss/INSPIRE/INSPIRE_NZ_HY_MZPMRP_WMS"
PIG = "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services"
BDOT = f"{PIG}/mapa_topo/bdot_10k/MapServer"
CBDH = f"{PIG}/hydrogeologia/cbdh_otwory/MapServer"
GZWP = f"{PIG}/hydrogeologia/gzwp/MapServer"
JCWPD = f"{PIG}/hydrogeologia/jcwpd/MapServer"
PODTOP = f"{PIG}/hydrogeologia/podtopienia/MapServer"
LIC_ISOK = "Dane publiczne PGW Wody Polskie (ISOK) – bezpłatne ponowne wykorzystanie"
LIC_PIG = "PIG-PIB – dane publiczne, bezpłatne do ponownego wykorzystania z podaniem źródła"
LIC_BDOT = "BDOT10k (PZGiK) – bezpłatne; kopia udostępniana przez PIG-PIB"
WATER_RADIUS_M = 1000
BORE_RADIUS_M = 3000

# BDOT10k: warstwa → (kind, opis)
BDOT_LAYERS = {33: ("stream", "ciek"), 34: ("stream", "ciek okresowy"), 32: ("ditch", "rów melioracyjny"),
               31: ("other", "kanał"), 30: ("pond", "woda powierzchniowa")}
REGION_TO_RZGW = {  # orientacyjnie: region wodny → Regionalny Zarząd Gospodarki Wodnej [DO_WERYFIKACJI]
    "warty": "RZGW w Poznaniu", "środkowej wisły": "RZGW w Warszawie", "górnej wisły": "RZGW w Krakowie",
    "dolnej wisły": "RZGW w Gdańsku", "małej wisły": "RZGW w Gliwicach", "górnej odry": "RZGW w Gliwicach",
    "środkowej odry": "RZGW we Wrocławiu", "dolnej odry i przymorza zachodniego": "RZGW w Szczecinie",
    "łaby": "RZGW we Wrocławiu", "niemna": "RZGW w Białymstoku", "pregoły": "RZGW w Gdańsku",
    "bugu": "RZGW w Lublinie", "górnej-wschodniej wisły": "RZGW w Rzeszowie",
    "środkowej-wschodniej wisły": "RZGW w Lublinie", "dolnej-wschodniej wisły": "RZGW w Białymstoku",
}


async def arcgis_query(url_layer: str, envelope: tuple[float, float, float, float], *, geometry: bool = True,
                       offset: float = 2.0, timeout_s: float = 8) -> list[dict]:
    minx, miny, maxx, maxy = envelope
    params = {"geometry": f"{minx},{miny},{maxx},{maxy}", "geometryType": "esriGeometryEnvelope",
              "inSR": 2180, "spatialRel": "esriSpatialRelIntersects", "outFields": "*",
              "returnGeometry": str(geometry).lower(), "outSR": 2180, "f": "json"}
    if geometry:
        params["maxAllowableOffset"] = offset
    r = await get_with_retry(f"{url_layer}/query", params=params, timeout_s=timeout_s)
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"ArcGIS: {j['error'].get('message')}")
    return j.get("features", [])


async def arcgis_identify(url: str, e: float, n: float, layers: str = "all") -> list[dict]:
    params = {"geometry": f"{e},{n}", "geometryType": "esriGeometryPoint", "sr": 2180, "layers": layers,
              "tolerance": 1, "mapExtent": f"{e - 500},{n - 500},{e + 500},{n + 500}",
              "imageDisplay": "100,100,96", "returnGeometry": "false", "f": "json"}
    r = await get_with_retry(f"{url}/identify", params=params, timeout_s=8)
    return r.json().get("results", [])


def esri_geom(g: dict) -> Any:
    if not g:
        return None
    if "x" in g:
        return Point(g["x"], g["y"])
    if "paths" in g:
        lines = [LineString(p) for p in g["paths"] if len(p) >= 2]
        return lines[0] if len(lines) == 1 else (shape({"type": "MultiLineString",
                                                         "coordinates": [list(ln.coords) for ln in lines]})
                                                 if lines else None)
    if "rings" in g:
        rings = [r for r in g["rings"] if len(r) >= 4]
        if not rings:
            return None
        polys = [Polygon(r) for r in rings]
        outer = max(polys, key=lambda p: p.area)
        holes = [p.exterior.coords for p in polys if p is not outer and outer.contains(p)]
        return Polygon(outer.exterior.coords, holes)
    return None


# ── strefy powodziowe ──
def _sld_rule(period: int, color: str) -> str:
    return ("<FeatureTypeStyle><Rule><ogc:Filter><ogc:PropertyIsEqualTo><ogc:PropertyName>loo_ql_returnperiod"
            f"</ogc:PropertyName><ogc:Literal>{period}</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter>"
            f'<PolygonSymbolizer><Fill><CssParameter name="fill">{color}</CssParameter></Fill>'
            "</PolygonSymbolizer></Rule></FeatureTypeStyle>")


# Styl serwerowy rysuje same obrysy → własny SLD z wypełnieniem: Q0,2% niebieski, Q1% zielony, Q10% czerwony
# (rysowane w tej kolejności, więc kolor piksela = najczęstszy scenariusz obejmujący to miejsce).
FLOOD_SLD = ('<?xml version="1.0" encoding="UTF-8"?><StyledLayerDescriptor version="1.0.0" '
             'xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"><NamedLayer>'
             "<Name>NZ.Fluvial</Name><UserStyle>" + _sld_rule(500, "#0000FF") + _sld_rule(100, "#00FF00")
             + _sld_rule(10, "#FF0000") + "</UserStyle></NamedLayer></StyledLayerDescriptor>")


async def flood_zone(parcel_2180: Any) -> tuple[str | None, bool, list[str]]:
    """→ (scenariusz najczęstszy '10%'|'1%'|'0.2%'|None, czy działka w jakiejkolwiek strefie, komunikaty).
    Jedno GetMap PNG z SLD_BODY w bbox działki (≈0,4 s) zamiast wolnego GetFeatureInfo (3–10 s)."""
    import warnings

    import numpy as np
    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile
    from shapely import contains_xy

    minx, miny, maxx, maxy = parcel_2180.buffer(5).bounds
    w_m, h_m = maxx - minx, maxy - miny
    px = max(w_m, h_m) / 250 if max(w_m, h_m) > 500 else 2.0
    W, H = max(8, int(w_m / px)), max(8, int(h_m / px))
    r = await get_with_retry(ISOK_WMS, params={
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap", "LAYERS": "NZ.Fluvial", "SRS": "EPSG:2180",
        "BBOX": f"{minx},{miny},{maxx},{maxy}", "WIDTH": W, "HEIGHT": H, "FORMAT": "image/png",
        "TRANSPARENT": "true", "FORMAT_OPTIONS": "antialias:none", "SLD_BODY": FLOOD_SLD}, timeout_s=9)
    if "image" not in r.headers.get("content-type", ""):
        raise RuntimeError(f"ISOK GetMap: {r.text[:200]}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile(r.content) as mf, mf.open() as ds:
            a = ds.read().astype(int)
    if a.shape[0] < 4:
        raise RuntimeError("ISOK GetMap: obraz bez kanału alfa")
    H, W = a.shape[1], a.shape[2]  # rzeczywisty rozmiar obrazu
    cols = minx + (np.arange(W) + 0.5) * (w_m / W)
    rows = maxy - (np.arange(H) + 0.5) * (h_m / H)
    XX, YY = np.meshgrid(cols, rows)
    inside = contains_xy(parcel_2180, XX, YY)
    n_in = max(1, int(inside.sum()))
    vis = (a[3] > 128) & inside
    red = vis & (a[0] > 180) & (a[1] < 90) & (a[2] < 90)
    green = vis & (a[1] > 180) & (a[0] < 90) & (a[2] < 90)
    blue = vis & (a[2] > 180) & (a[0] < 90) & (a[1] < 90)
    shares = {"10%": red.sum() / n_in, "1%": green.sum() / n_in, "0.2%": blue.sum() / n_in}
    if not vis.any():
        return None, False, []
    msgs = ["Działka leży (w całości lub w części) w obszarze zagrożenia powodziowego (MZP): " + ", ".join(
        f"scenariusz {k} – ok. {v:.0%} powierzchni" for k, v in shares.items() if v > 0) + "."]
    for lab in ("10%", "1%", "0.2%"):
        if shares[lab] > 0:
            return lab, True, msgs
    return None, True, msgs


# ── wody powierzchniowe ──
async def nearest_waters(parcel_2180: Any) -> list[WaterFeature]:
    env = parcel_2180.buffer(WATER_RADIUS_M).bounds
    res = await asyncio.gather(*(arcgis_query(f"{BDOT}/{lid}", env) for lid in BDOT_LAYERS),
                               return_exceptions=True)
    feats: list[tuple[float, WaterFeature]] = []
    errors = 0
    for lid, fs in zip(BDOT_LAYERS, res):
        if isinstance(fs, Exception):
            errors += 1
            continue
        kind, label = BDOT_LAYERS[lid]
        for f in fs:
            g = esri_geom(f.get("geometry"))
            if g is None or g.is_empty:
                continue
            a = f.get("attributes", {})
            k = kind
            if lid == 30:
                code = a.get("X_KOD")
                area = g.area
                k = "river" if code == "PTWP02" else ("lake" if area >= 50_000 else "pond")
                label_ = {"river": "rzeka (woda płynąca)", "lake": "jezioro / zbiornik", "pond": "staw / oczko"}[k]
            elif lid == 33 and str(a.get("RODZAJ", "")).lower().startswith("rz"):
                k, label_ = "river", "rzeka"
            else:
                label_ = label
            d = float(g.distance(parcel_2180))
            if d > WATER_RADIUS_M:
                continue
            gg = to_4326(g.simplify(3))
            feats.append((d, WaterFeature(kind=k, name=a.get("NAZWA") or label_, distance_m=round(d),
                                          geometry=GeoJSONGeometry(**mapping(gg)))))
    if errors == len(BDOT_LAYERS):
        raise RuntimeError("BDOT10k niedostępne")
    feats.sort(key=lambda t: t[0])
    # najbliższy obiekt każdego rodzaju + reszta najbliższych (max 12)
    out, seen = [], set()
    for d, wf in feats:
        if wf.kind not in seen:
            out.append(wf); seen.add(wf.kind)
    for d, wf in feats:
        if len(out) >= 12:
            break
        if wf not in out:
            out.append(wf)
    return sorted(out, key=lambda w: w.distance_m)


async def boreholes(parcel_2180: Any) -> list[dict]:
    fs = await arcgis_query(f"{CBDH}/0", parcel_2180.buffer(BORE_RADIUS_M).bounds)
    rows = []
    for f in fs:
        a, g = f.get("attributes", {}), esri_geom(f.get("geometry"))
        if g is None:
            continue
        p = to_4326(g)
        rows.append({"name": a.get("NAZWA"), "distance_m": round(g.distance(parcel_2180)),
                     "depth_m": a.get("GLEBOKOSC"), "year": a.get("DATA_WYKONANIA"),
                     "type": a.get("TYP_OTWORU"), "purpose": a.get("PRZEZNACZENIE_OTWORU"),
                     "locality": a.get("MIEJSCOWOSC"), "decommissioned": a.get("ZLIKWIDOWANY") == "Tak",
                     "lon": round(p.x, 6), "lat": round(p.y, 6)})
    rows.sort(key=lambda r: r["distance_m"])
    return rows[:5]


class HydrologyConnector(Connector):
    key = "hydrology"
    title = "Wody powierzchniowe i podziemne"
    category = "hydro"
    live_ttl_s = 30 * 24 * 3600
    timeout_s = 15
    cache_version = 2

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        parcel = to_2180(shape(ctx.parcel.geometry.model_dump()))
        c = parcel.representative_point()
        t_flood, t_water, t_bore, t_gzwp, t_jcwpd, t_podt = await asyncio.gather(
            flood_zone(parcel), nearest_waters(parcel), boreholes(parcel),
            arcgis_identify(GZWP, c.x, c.y), arcgis_identify(JCWPD, c.x, c.y, "all:2,5"),
            arcgis_identify(PODTOP, c.x, c.y), return_exceptions=True)
        info = HydrologyInfo()
        msgs: list[str] = []
        unc: list[str] = []
        provs = []
        ok_parts = 0

        if isinstance(t_flood, Exception):
            msgs.append(f"ISOK (strefy powodziowe) niedostępne: {type(t_flood).__name__}.")
            unc.append("Nie sprawdzono stref zagrożenia powodziowego – źródło nie odpowiedziało.")
        else:
            zone, any_hit, fm = t_flood
            info.in_flood_zone, info.flood_zone_checked, info.in_flood_hazard_area = zone, True, any_hit
            msgs += fm
            ok_parts += 1
            provs.append(self.prov("ISOK / PGW Wody Polskie – mapy zagrożenia powodziowego (MZP)",
                                   source_url=ISOK_WMS, licence=LIC_ISOK,
                                   notes="warstwa NZ.Fluvial (cykl MZP 2022), scenariusze Q10%, Q1%, Q0,2%; GetMap z własnym SLD"))
            unc.append("Brak strefy na mapach zagrożenia powodziowego nie wyklucza lokalnych podtopień "
                       "(mapy obejmują tylko rzeki objęte MZP).")
        if isinstance(t_water, Exception):
            msgs.append(f"BDOT10k (cieki, rowy) niedostępne: {type(t_water).__name__}.")
        else:
            info.nearest_water = t_water
            ok_parts += 1
            provs.append(self.prov("BDOT10k – sieć wodna (kopia w usłudze PIG-PIB)", source_url=BDOT,
                                   licence=LIC_BDOT, notes=f"promień {WATER_RADIUS_M} m"))
            unc.append("Sieć rowów i cieków z BDOT10k (aktualność głównie 2012–2015) – rowy mogły zostać "
                       "zasypane lub wykopane później; nazwy cieków nie są dostępne w tej usłudze.")
        if isinstance(t_bore, Exception):
            msgs.append(f"CBDH (otwory) niedostępne: {type(t_bore).__name__}.")
        else:
            info.nearest_boreholes = t_bore
            ok_parts += 1
            provs.append(self.prov("PIG-PIB – Centralna Baza Danych Hydrogeologicznych (CBDH)", source_url=CBDH,
                                   licence=LIC_PIG, notes=f"promień {BORE_RADIUS_M} m"))
            unc.append("Dla otworów publiczna usługa podaje głębokość i typ, ale nie poziom wody ani "
                       "wydajność – te dane są w kartach otworów CBDH (geoportal PIG-PIB).")
        if not isinstance(t_gzwp, Exception):
            ok_parts += 1
            if t_gzwp:
                a = t_gzwp[0]["attributes"]
                depth = a.get("Głębokość średnia [m]")
                depth_txt = f", śr. głębokość ok. {depth} m" if depth not in (None, "", "0", "Null") else ""
                info.gzwp = f"GZWP nr {a.get('Nr GZWP')} „{a.get('Nazwa GZWP')}” ({a.get('Typ ośrodka', '')}{depth_txt})"
            provs.append(self.prov("PIG-PIB – Główne Zbiorniki Wód Podziemnych (GZWP)", source_url=GZWP,
                                   licence=LIC_PIG))
        if not isinstance(t_jcwpd, Exception) and t_jcwpd:
            best = sorted(t_jcwpd, key=lambda r: 0 if r["layerId"] == 2 else 1)[0]["attributes"]
            region = (best.get("Region wodny") or "").strip()
            region_name = region if region.lower().startswith("region") else f"region wodny {region}"
            info.jcwpd_code = best.get("Kod UE")
            info.catchment_name = f"{region_name} (dorzecze: {best.get('Dorzecze')})" if region else None
            key = region_name.lower().replace("region wodny ", "")
            rzgw = REGION_TO_RZGW.get(key)
            info.water_management_board = (
                f"PGW Wody Polskie – {rzgw} (wg regionu wodnego; właściwy Zarząd Zlewni i Nadzór Wodny "
                "sprawdź na wody.gov.pl)" if rzgw else
                "PGW Wody Polskie – właściwy Zarząd Zlewni i Nadzór Wodny sprawdź na wody.gov.pl")
            unc.append("Zarząd Wód Polskich ustalony orientacyjnie z regionu wodnego (DO_WERYFIKACJI) – "
                       "usługi Wód Polskich z granicami zarządów zlewni wymagają logowania (HTTP 401).")
            provs.append(self.prov("PIG-PIB – Jednolite Części Wód Podziemnych (JCWPd 2022–2027)",
                                   source_url=JCWPD, licence=LIC_PIG))
        if not isinstance(t_podt, Exception):
            info.in_groundwater_flood_area = bool(t_podt)
            provs.append(self.prov("PIG-PIB – obszary zagrożone podtopieniami", source_url=PODTOP, licence=LIC_PIG))
        info.groundwater_depth_m = None
        unc.append("Głębokości do pierwszego poziomu wód podziemnych (Mapa Hydrogeologiczna Polski 1:50 000) nie "
                   "pokazujemy – usługa PIG-PIB wymaga tokena. Przed budową studni sprawdź kartę MHP lub "
                   "otwory w okolicy.")
        if ok_parts == 0:
            return self.block(BlockStatus.error, messages=msgs,
                              uncertainty=["Żadne źródło danych hydrologicznych nie odpowiedziało."])
        status = BlockStatus.ok if ok_parts >= 4 else BlockStatus.partial
        return self.block(status, info, provenance=provs, uncertainty=unc, messages=msgs)
