"""Gleba → SoilInfo.

Źródła (w kolejności):
  1) IUNG-PIB „Kategorie podatności gleb na suszę” (raster, te same kategorie 1–4 co SMSR) –
     GeoServer WMS `Susza:katgl_landuse2024`, GetFeatureInfo (application/json, GRAY_INDEX).
  2) GUGiK/IUNG Mapa glebowo-rolnicza 1:5000 – ArcGIS WMS, warstwa 0 KONTURY_GLEBOWE (text/xml):
     kompleks przydatności rolniczej, typ/podtyp gleby, gatunki (uziarnienie) PODLOZE1..5.
  3) Fallback ISRIC SoilGrids v2 (250 m) – clay/sand/silt/SOC → TAW (Saxton & Rawls 2006) [SZACUNEK].
Próbkujemy do 5 punktów wewnątrz działki i raportujemy udziały.
"""
from __future__ import annotations

import asyncio
import json
from collections import Counter
from typing import Any

from shapely.geometry import shape

from app.connectors.base import Connector
from app.contracts.models import AnalysisContext, BlockStatus, DataBlock, SoilInfo
from app.core.geo import _tf, sample_points_2180
from app.core.http import RateLimited, get_with_retry
from app.core.ogc import esri_xml_fields, wms_feature_info

IUNG_WMS = "https://sgeo.iung.pl/geoserver/wms"
IUNG_LAYER = "Susza:katgl_landuse2024"
MGR_WMS = "https://mapy.geoportal.gov.pl/wss/service/pub/guest/MapaGlebowoRolnicza/MapServer/WMSServer"
SOILGRIDS = "https://rest.isric.org/soilgrids/v2.0/properties/query"

KATGL_LABELS = {
    1: "kategoria I – bardzo podatna na suszę (gleby bardzo lekkie)",
    2: "kategoria II – podatna na suszę (gleby lekkie)",
    3: "kategoria III – średnio podatna na suszę (gleby średnie)",
    4: "kategoria IV – mało podatna na suszę (gleby ciężkie)",
    5: "gleby organiczne",
    11: "lasy, zadrzewienia", 12: "wody", 13: "tereny zabudowane", 14: "tereny komunikacyjne, nieużytki",
    19: "tereny niesklasyfikowane", 99: "tereny niesklasyfikowane",
}
# Woda ogólnie dostępna (WOD) wg kategorii SMSR (Ślusarczyk 1979) – środek przedziału, mm [SZACUNEK]
KATGL_WOD_MM = {1: 110.0, 2: 150.0, 3: 186.0, 4: 220.0}

COMPLEX = {
    "1": "pszenny bardzo dobry", "2": "pszenny dobry", "3": "pszenny wadliwy", "4": "żytni bardzo dobry",
    "5": "żytni dobry", "6": "żytni słaby", "7": "żytni bardzo słaby", "8": "zbożowo-pastewny mocny",
    "9": "zbożowo-pastewny słaby", "10": "pszenny górski", "11": "zbożowy górski",
    "12": "owsiano-ziemniaczany górski", "13": "owsiano-pastewny górski",
    "14": "grunty orne przeznaczone pod użytki zielone",
    "1z": "użytki zielone bardzo dobre i dobre", "2z": "użytki zielone średnie",
    "3z": "użytki zielone słabe i bardzo słabe",
    "Ls": "lasy", "Lz": "zadrzewienia i zakrzewienia", "N": "nieużytki", "W": "wody", "Wsr": "wody",
}
SOIL_TYPE = {
    "A": "gleby bielicowe i pseudobielicowe", "B": "gleby brunatne właściwe", "Bw": "gleby brunatne wyługowane",
    "Bk": "gleby brunatne kwaśne", "C": "czarnoziemy", "D": "czarne ziemie",
    "Dz": "czarne ziemie zdegradowane i szare ziemie", "G": "gleby glejowe", "F": "mady rzeczne",
    "Fł": "mady łąkowe", "Fm": "mady morskie", "E": "gleby mułowo-torfowe", "T": "gleby torfowe",
    "M": "gleby murszowo-mineralne i murszaste", "Mt": "gleby torfowo-murszowe", "R": "rędziny",
    "Cd": "czarnoziemy zdegradowane", "Rc": "rędziny czarnoziemne", "Rb": "rędziny brunatne", "S": "gleby słone", "Ł": "gleby deluwialne",
}
TEXTURE = {
    "pl": ("piasek luźny", 1), "plp": ("piasek luźny pylasty", 1), "ps": ("piasek słabo gliniasty", 1),
    "psp": ("piasek słabo gliniasty pylasty", 1), "pgl": ("piasek gliniasty lekki", 2),
    "pglp": ("piasek gliniasty lekki pylasty", 2), "pgm": ("piasek gliniasty mocny", 2),
    "pgmp": ("piasek gliniasty mocny pylasty", 2), "gl": ("glina lekka", 3), "glp": ("glina lekka pylasta", 3),
    "płg": ("pył gliniasty", 3), "płz": ("pył zwykły", 3), "płp": ("pył piaszczysty", 3),
    "gs": ("glina średnia", 4), "gsp": ("glina średnia pylasta", 4), "gc": ("glina ciężka", 4),
    "gcp": ("glina ciężka pylasta", 4), "płi": ("pył ilasty", 4), "i": ("ił", 4), "ip": ("ił pylasty", 4),
    "ż": ("żwir", 1), "pr": ("piasek", 1), "l": ("less", 3), "li": ("less ilasty", 4),
}
LIC_IUNG = "IUNG-PIB – udostępnione publicznie w SMSR (susza.iung.pulawy.pl); przypisanie źródła"
LIC_GUGIK = "Dane PZGiK – bezpłatne (art. 40a Prawa geodezyjnego i kartograficznego)"
LIC_SG = "CC BY 4.0 (ISRIC SoilGrids)"


def _complex_key(code: str | None) -> str | None:
    if not code:
        return None
    c = code.strip().lower()
    return c if c in COMPLEX else code.strip()


def _soil_type_label(code: str) -> str:
    for i in range(len(code), 0, -1):  # najdłuższy znany prefiks, np. "Emt" → "E"
        if code[:i] in SOIL_TYPE:
            return f"{SOIL_TYPE[code[:i]]} ({code})"
    return f"kod gleby {code}"


def _texture_label(code: str) -> str:
    return TEXTURE.get(code, (code, None))[0]


def saxton_rawls_taw_mm(layers: list[tuple[float, float, float, float]]) -> float | None:
    """TAW [mm] z warstw (grubość_mm, sand_frac, clay_frac, OM_%) – Saxton & Rawls (2006), θ33 − θ1500."""
    total = 0.0
    for thick, S, C, OM in layers:
        t1500t = -0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM + 0.068 * S * C + 0.031
        t1500 = t1500t + (0.14 * t1500t - 0.02)
        t33t = (-0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM + 0.452 * S * C + 0.299)
        t33 = t33t + (1.283 * t33t ** 2 - 0.374 * t33t - 0.015)
        total += max(t33 - t1500, 0.0) * thick
    return round(total, 0) if layers else None


async def _iung_category(e: float, n: float) -> int | None:
    body = await wms_feature_info(IUNG_WMS, IUNG_LAYER, e, n, info_format="application/json", half_m=10, timeout_s=6)
    feats = json.loads(body).get("features") or []
    if not feats:
        return None
    v = feats[0].get("properties", {}).get("GRAY_INDEX")
    v = int(v) if v is not None else None
    return None if v in (0, 255) else v


async def _mgr_contour(e: float, n: float) -> dict[str, str] | None:
    body = await wms_feature_info(MGR_WMS, "0", e, n, info_format="text/xml", half_m=10, timeout_s=6)
    rows = esri_xml_fields(body)
    return rows[0] if rows else None


async def _soilgrids(lon: float, lat: float) -> dict[str, Any]:
    params = [("lon", lon), ("lat", lat), ("value", "mean")]
    params += [("property", p) for p in ("clay", "sand", "silt", "soc")]
    params += [("depth", d) for d in ("0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm")]
    r = await get_with_retry(SOILGRIDS, params=params, timeout_s=8, attempts=1)  # type: ignore[arg-type]
    layers = r.json()["properties"]["layers"]
    out: dict[str, dict[str, float]] = {}
    for L in layers:
        d = L["unit_measure"]["d_factor"]
        for dep in L["depths"]:
            v = dep["values"].get("mean")
            if v is not None:
                out.setdefault(dep["label"], {})[L["name"]] = v / d
    return out


def _soilgrids_summary(sg: dict[str, dict[str, float]]) -> dict[str, float | None]:
    thick = {"0-5cm": 50, "5-15cm": 100, "15-30cm": 150, "30-60cm": 300, "60-100cm": 400}
    layers, top = [], sg.get("0-5cm") or {}
    for lab, t in thick.items():
        v = sg.get(lab)
        if not v or v.get("sand") is None or v.get("clay") is None:
            continue
        om = (v.get("soc") or 0) * 1.724 / 10  # SOC g/kg → materia organiczna %
        layers.append((t, v["sand"] / 100, v["clay"] / 100, min(om, 8)))
    # wartości 0–30 cm (warstwa orna) jako średnia ważona
    def topavg(prop: str) -> float | None:
        acc = w = 0.0
        for lab, t in (("0-5cm", 5), ("5-15cm", 10), ("15-30cm", 15)):
            x = (sg.get(lab) or {}).get(prop)
            if x is not None:
                acc += x * t; w += t
        return round(acc / w, 1) if w else None
    return {"clay": topavg("clay"), "sand": topavg("sand"), "silt": topavg("silt"), "soc": topavg("soc"),
            "taw": saxton_rawls_taw_mm(layers) if layers else None, "_top": bool(top)}


def _shares(values: list[Any]) -> dict[str, float]:
    c = Counter(v for v in values if v is not None)
    tot = sum(c.values())
    return {str(k): round(100 * v / tot, 0) for k, v in c.most_common()} if tot else {}


class SoilConnector(Connector):
    key = "soil"
    title = "Gleba"
    category = "soil"
    live_ttl_s = 30 * 24 * 3600
    timeout_s = 12
    cache_version = 2

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        geom = shape(ctx.parcel.geometry.model_dump())
        pts = sample_points_2180(geom, n=5)
        inv = _tf(2180, 4326)
        lon, lat = ctx.parcel.centroid
        messages: list[str] = []
        unc: list[str] = []

        cat_tasks = [_iung_category(e, n) for e, n in pts]
        mgr_tasks = [_mgr_contour(e, n) for e, n in pts]
        sg_task = asyncio.create_task(_soilgrids(lon, lat))
        res = await asyncio.gather(*cat_tasks, *mgr_tasks, return_exceptions=True)
        cats, mgrs = res[:len(pts)], res[len(pts):]

        cat_err = [r for r in cats if isinstance(r, Exception)]
        mgr_err = [r for r in mgrs if isinstance(r, Exception)]
        if cat_err:
            messages.append(f"IUNG kategorie gleb: {len(cat_err)}/{len(pts)} zapytań nieudanych "
                            f"({type(cat_err[0]).__name__}).")
        if mgr_err:
            messages.append(f"Mapa glebowo-rolnicza: {len(mgr_err)}/{len(pts)} zapytań nieudanych "
                            f"({type(mgr_err[0]).__name__}).")

        samples = []
        cat_vals, cx_vals, type_vals, tex_profiles = [], [], [], []
        for (e, n), c, m in zip(pts, cats, mgrs):
            c = None if isinstance(c, Exception) else c
            m = None if isinstance(m, Exception) else m
            plon, plat = inv.transform(e, n)
            smp: dict[str, Any] = {"lon": round(plon, 6), "lat": round(plat, 6), "drought_category": c}
            if c is not None:
                cat_vals.append(c)
            if m:
                cx = _complex_key(m.get("KOMPLEKS_NR") or m.get("KOMPLEKS"))
                tp = m.get("TYPPODTYP_NR") or m.get("TYPPODTYP")
                tex = [m[f"PODLOZE{i}"] for i in range(1, 6) if m.get(f"PODLOZE{i}") not in (None, ".")]
                smp.update(agri_complex=cx, soil_type=tp, texture=tex,
                           flood_terrain=m.get("TERENZALEWOWY") == "true")
                cx_vals.append(cx); type_vals.append(tp); tex_profiles.append(tuple(tex))
            samples.append(smp)

        info = SoilInfo(samples=samples)
        awc_from_sg = False
        provs = []
        # kategoria podatności na suszę (IUNG) – źródło główne dla SMSR
        mineral = [c for c in cat_vals if c in (1, 2, 3, 4)]
        if cat_vals:
            shares = _shares(cat_vals)
            info.drought_category_shares_pct = {
                (k if int(k) in (1, 2, 3, 4) else KATGL_LABELS.get(int(k), k)): v for k, v in shares.items()}
            if mineral:
                dom = Counter(mineral).most_common(1)[0][0]
                info.drought_category = dom
                info.drought_susceptibility = KATGL_LABELS[dom]
                info.awc_mm = KATGL_WOD_MM[dom]
            else:
                dom_any = Counter(cat_vals).most_common(1)[0][0]
                info.drought_susceptibility = KATGL_LABELS.get(dom_any, str(dom_any))
                unc.append("Kategorii podatności na suszę nie wyznaczono dla tej działki (wg IUNG to nie jest "
                           "grunt rolny na glebie mineralnej) – progi suszy SMSR mogą nie mieć zastosowania.")
            provs.append(self.prov("IUNG-PIB – Mapa kategorii podatności gleb na suszę (SMSR)",
                                   source_url=f"{IUNG_WMS}?layers={IUNG_LAYER}", licence=LIC_IUNG,
                                   notes=f"GetFeatureInfo w {len(pts)} punktach działki"))
        if cx_vals:
            cx_dom = Counter(cx_vals).most_common(1)[0][0]
            info.agri_complex_code = cx_dom
            info.agri_complex = (f"{COMPLEX.get(cx_dom, 'kompleks ' + str(cx_dom))} ({cx_dom})" if cx_dom else None)
            info.agri_complex_shares_pct = _shares(cx_vals)
            tp_dom = Counter(t for t in type_vals if t).most_common(1)
            if tp_dom:
                code = tp_dom[0][0]
                info.soil_type = _soil_type_label(code)
            prof = Counter(p for p in tex_profiles if p).most_common(1)
            if prof:
                info.texture_profile = list(prof[0][0])
                info.texture_class = " na ".join(_texture_label(t) for t in prof[0][0][:2])
            provs.append(self.prov("GUGiK – Mapa glebowo-rolnicza 1:5000 (IUNG)", source_url=MGR_WMS,
                                   licence=LIC_GUGIK, notes="warstwa KONTURY_GLEBOWE"))
            if not cat_vals and info.texture_profile:
                tc = [TEXTURE.get(t, (None, None))[1] for t in info.texture_profile[:3]]
                tc = [x for x in tc if x]
                if tc:
                    est = min(tc)  # ostrożnie: najlżejsza warstwa decyduje o podatności
                    info.drought_category = est
                    info.drought_susceptibility = KATGL_LABELS[est] + " [SZACUNEK z uziarnienia]"
                    info.awc_mm = KATGL_WOD_MM[est]
                    unc.append("Kategoria podatności na suszę oszacowana z gatunku gleby (uziarnienia), bo mapa "
                               "kategorii IUNG nie odpowiedziała – SZACUNEK.")

        # SoilGrids: uzupełnienie (% iłu/piasku, węgiel) albo fallback
        try:
            sg = _soilgrids_summary(await asyncio.wait_for(sg_task, timeout=5))
            if sg["_top"]:
                info.clay_pct, info.sand_pct, info.silt_pct, info.soc_g_kg = (
                    sg["clay"], sg["sand"], sg["silt"], sg["soc"])
                if info.awc_mm is None and sg["taw"] is not None:
                    info.awc_mm = sg["taw"]
                    awc_from_sg = True
                    unc.append("Zapas wody dostępnej (TAW) policzony z SoilGrids (250 m) wzorem Saxtona i Rawlsa "
                               "(2006) – SZACUNEK, może odbiegać od gleby na Twoim polu.")
                provs.append(self.prov("ISRIC SoilGrids v2.0 (250 m)", source_url=SOILGRIDS, licence=LIC_SG,
                                       notes="średnie 0–30 cm; model globalny"))
        except RateLimited:
            messages.append("SoilGrids: limit zapytań (429).")
        except Exception as e:  # noqa: BLE001
            sg_task.cancel()
            messages.append(f"SoilGrids niedostępne ({type(e).__name__}).")

        if not provs:
            return self.block(BlockStatus.error, messages=messages,
                              uncertainty=["Żadne źródło danych glebowych nie odpowiedziało."])
        if not cx_vals and not cat_vals:
            info.source_used = "soilgrids"
            unc.append("Brak działki na mapie glebowo-rolniczej (np. luki w podkarpackim, tereny nierolne) – "
                       "pokazujemy wyłącznie globalny model SoilGrids (250 m) – SZACUNEK.")
            status = BlockStatus.partial
        else:
            info.source_used = "iung_katgl+mgr" if cx_vals and cat_vals else ("iung_katgl" if cat_vals else "mgr")
            status = BlockStatus.ok if (cx_vals and cat_vals) else BlockStatus.partial
        if info.awc_mm is not None and not awc_from_sg:
            unc.append(f"Zapas wody dostępnej ≈ {info.awc_mm:.0f} mm to typowa wartość dla kategorii gleby "
                       "(środek przedziału WOD wg IUNG), a nie pomiar na Twoim polu – SZACUNEK.")
        unc.append("Mapa glebowo-rolnicza powstała głównie w latach 60.–80. XX w. – stan gleby mógł się zmienić "
                   "(erozja, melioracje, materia organiczna).")
        if len(set(cat_vals)) > 1 or len(set(cx_vals)) > 1:
            unc.append("Gleba w obrębie działki jest zróżnicowana – patrz udziały kategorii i kompleksów.")
        if not ctx.parcel.area_ha or len(pts) < 3:
            unc.append(f"Działka mała – sprawdzono {len(pts)} punkt(y).")
        return self.block(status, info, provenance=provs, uncertainty=unc, messages=messages)
