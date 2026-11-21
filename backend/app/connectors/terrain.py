"""Rzeźba terenu → TerrainInfo (górka / stok / dołek, spadek, zagłębienia, linie spływu, TWI).

Źródło: NMT GUGiK (z lotniczego skanowania laserowego, siatka 1 m) przez usługę wysokości
`https://services.gugik.gov.pl/nmt/?request=GetHByPointList` (POST, lista punktów „N E” w EPSG:2180).
Pobieramy regularną siatkę punktów (krok 5–15 m) w bbox działki + 300 m. Usługa WCS NMT
(`.../NMT/GRID1/WCS/...`) 21.11.2026 nie odpowiadała na GetCoverage (zawieszenie po TLS) – opis w docs.
Obliczenia: `science/terrain.py` (numpy/scipy).
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import numpy as np
from shapely import contains_xy
from shapely.geometry import LineString, mapping, shape
from shapely.ops import linemerge, unary_union

from app.config import settings
from app.connectors.base import Connector
from app.contracts.models import AnalysisContext, BlockStatus, DataBlock, TerrainInfo
from app.core.geo import to_2180, to_4326
from app.core.http import get_client, get_with_retry
from app.science import terrain as T

log = logging.getLogger(__name__)
NMT_POINTS = "https://services.gugik.gov.pl/nmt/"
LIC = "Dane PZGiK – bezpłatne, dowolny cel (art. 40a Prawa geodezyjnego i kartograficznego)"
MAX_POINTS = 7_000
CHUNK = 1_000  # usługa zwraca wysokości tylko dla ~1000 pierwszych punktów żądania
NMT_PARALLEL = 3  # więcej równoległych zapytań → usługa zaczyna zwracać niepełne odpowiedzi


# Krok siatki tylko z ustalonych poziomów, a początek siatki przyciągnięty do wielokrotności kroku
# w EPSG:2180 – sąsiednie działki dostają TE SAME punkty NMT, więc zagłębienia i linie spływu w części
# wspólnej się pokrywają (wcześniej siatka była zakotwiczona w rogu bbox każdej działki osobno).
CELL_LEVELS = (5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0)
EDGE_MARGIN_M = 150.0  # obiekty dalej niż tyle od działki są zależne od brzegu okna – nie pokazujemy ich


def snapped_grid(bounds: tuple[float, float, float, float], max_points: int = MAX_POINTS,
                 min_cell: float = 5.0) -> tuple[tuple[float, float, float, float], float, int, int]:
    """Zwraca (bbox przyciągnięty do kratki, krok, liczba wierszy, liczba kolumn)."""
    minx, miny, maxx, maxy = bounds
    for cell in CELL_LEVELS:
        if cell < min_cell:
            continue
        x0, y0 = math.floor(minx / cell) * cell, math.floor(miny / cell) * cell
        x1, y1 = math.ceil(maxx / cell) * cell, math.ceil(maxy / cell) * cell
        ncols, nrows = int(round((x1 - x0) / cell)) + 1, int(round((y1 - y0) / cell)) + 1
        if nrows * ncols <= max_points:
            break
    return (x0, y0, x1, y1), cell, nrows, ncols


def grid_spec(bounds: tuple[float, float, float, float], max_points: int = MAX_POINTS,
              min_cell: float = 5.0) -> tuple[float, int, int]:
    _, cell, nrows, ncols = snapped_grid(bounds, max_points, min_cell)
    return cell, nrows, ncols


def parse_heights(text: str) -> list[float | None]:
    out: list[float | None] = []
    for tok in text.strip().split(","):
        parts = tok.split()
        try:
            v = float(parts[2]) if len(parts) >= 3 else None
        except ValueError:
            v = None
        out.append(None if v is None or v < -100 or v > 3000 else v)
    return out


async def fetch_grid(bounds: tuple[float, float, float, float], cell: float, nrows: int,
                     ncols: int) -> np.ndarray:
    minx, miny, maxx, maxy = bounds
    # wiersz 0 = północ
    pts = [(maxy - r * cell, minx + c * cell) for r in range(nrows) for c in range(ncols)]
    chunks = [pts[i:i + CHUNK] for i in range(0, len(pts), CHUNK)]

    sem = asyncio.Semaphore(NMT_PARALLEL)

    blocked = asyncio.Event()

    async def ask(ch: list[tuple[float, float]]) -> list[float | None] | None:
        if blocked.is_set():
            return None
        body = ",".join(f"{n:.0f} {e:.0f}" for n, e in ch)
        try:
            async with sem:
                # bez podążania za przekierowaniem: przy przeciążeniu / limicie z jednego IP GUGiK odsyła 302 na
                # integracja01…/resp/nmt.php, która zwraca megabajty binarnych śmieci (stąd „oczekiwano 1000, otrzymano 1”)
                r = await get_client().post(NMT_POINTS, data={"request": "GetHByPointList", "list": body},
                                            timeout=8, follow_redirects=False)
        except Exception:  # noqa: BLE001 – błąd sieci: spróbujemy mniejszą paczką
            return None
        if r.status_code in (301, 302, 303, 307, 429) or r.status_code >= 500:
            blocked.set()          # usługa odmawia – nie męczymy jej dalej, przechodzimy na DEM zapasowy
            return None
        vals = parse_heights(r.text)
        return vals if len(vals) == len(ch) else None

    async def one(ch: list[tuple[float, float]], depth: int = 0) -> list[float | None]:
        # Usługa przy obciążeniu zwraca czasem 1 wartość/komunikat zamiast listy (ValueError „oczekiwano 1000,
        # otrzymano 1”). Ponawiamy z przerwą, a potem dzielimy paczkę na pół; co się nie uda → NaN (status partial).
        for attempt in range(2):
            vals = await ask(ch)
            if vals is not None:
                return vals
            await asyncio.sleep(0.4 * (attempt + 1))
        if blocked.is_set():
            return [None] * len(ch)
        if depth < 2 and len(ch) > 50:
            half = len(ch) // 2
            a, b = await asyncio.gather(one(ch[:half], depth + 1), one(ch[half:], depth + 1))
            return a + b
        return [None] * len(ch)

    res = await asyncio.gather(*(one(ch) for ch in chunks))
    flat = [np.nan if v is None else v for part in res for v in part]
    return np.array(flat, dtype=float).reshape(nrows, ncols)


COPDEM_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
COPDEM_SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/cop-dem-glo-30"
LIC_COPDEM = "Copernicus DEM GLO-30 © DLR e.V. 2010–2014 i Airbus 2014–2018, licencja Copernicus (bezpłatnie, z podaniem źródła)"


async def fetch_grid_copdem(bounds: tuple[float, float, float, float], cell: float, nrows: int,
                            ncols: int) -> np.ndarray:
    """Zapasowy DEM: Copernicus GLO-30 (30 m, DSM) z Planetary Computer, próbkowany w punktach naszej siatki."""
    import rasterio
    from shapely.geometry import box
    minx, miny, maxx, maxy = bounds
    bb = to_4326(box(minx, miny, maxx, maxy)).bounds
    r = await get_client().post(COPDEM_STAC, json={"collections": ["cop-dem-glo-30"], "bbox": list(bb), "limit": 4},
                                timeout=8)
    r.raise_for_status()
    feats = r.json().get("features") or []
    if not feats:
        raise RuntimeError("Copernicus DEM: brak kafla dla obszaru")
    token = (await get_with_retry(COPDEM_SAS, timeout_s=6)).json()["token"]
    hrefs = [f"{f['assets']['data']['href']}?{token}" for f in feats]
    ys = [maxy - rr * cell for rr in range(nrows)]
    xs = [minx + cc * cell for cc in range(ncols)]
    from shapely import points as _points
    pts = to_4326(_points([(x, y) for y in ys for x in xs]))
    coords = [(p.x, p.y) for p in pts]

    def _sample() -> np.ndarray:
        out = np.full(len(coords), np.nan)
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="10"):
            for href in hrefs:
                with rasterio.open(href) as ds:
                    l, b, rgt, t = ds.bounds
                    idx = [i for i, (x, y) in enumerate(coords) if np.isnan(out[i]) and l <= x <= rgt and b <= y <= t]
                    if not idx:
                        continue
                    for i, v in zip(idx, ds.sample([coords[i] for i in idx])):
                        val = float(v[0])
                        out[i] = val if -100 < val < 3000 else np.nan
        return out.reshape(nrows, ncols)

    return await asyncio.to_thread(_sample)


def _mask_to_polys(mask: np.ndarray, transform: Any) -> list:
    from rasterio import features
    return [shape(g) for g, v in features.shapes(mask.astype("uint8"), mask=mask, transform=transform)
            if v == 1]


def analyse(z: np.ndarray, cell: float, origin: tuple[float, float], parcel_2180: Any) -> dict[str, Any]:
    """Cała analiza na siatce; zwraca słownik pól TerrainInfo (geometrie w EPSG:2180)."""
    from rasterio.transform import from_origin
    from scipy import ndimage

    x0, y0 = origin  # lewy górny róg (środek komórki [0,0])
    nrows, ncols = z.shape
    nan_share = float(np.isnan(z).mean())
    z = T.fill_nan(z)
    xs = x0 + np.arange(ncols) * cell
    ys = y0 - np.arange(nrows) * cell
    XX, YY = np.meshgrid(xs, ys)
    inside = contains_xy(parcel_2180, XX, YY)
    if inside.sum() < 1:  # działka mniejsza niż komórka – najbliższa komórka
        c = parcel_2180.representative_point()
        inside[int(round((y0 - c.y) / cell)), int(round((c.x - x0) / cell))] = True

    slope, aspect = T.slope_aspect(z, cell)
    tpi_r = T.tpi(z, cell, radius_m=150)
    zf = T.priority_flood(z, eps=0.0)
    depth = zf - z
    zf_eps = T.priority_flood(z, eps=1e-3)
    fd, acc = T.d8_accumulation(zf_eps)
    twi = T.twi(acc, slope, cell)

    # zagłębienia: głębokość ≥ 0,2 m i pow. ≥ 200 m²
    transform = from_origin(x0 - cell / 2, y0 + cell / 2, cell, cell)
    lab, nlab = ndimage.label(depth > 0.05)
    dep_feats = []
    min_cells = max(1, int(200 / cell ** 2))
    in_dep = np.zeros_like(inside)
    for i in range(1, nlab + 1):
        m = lab == i
        if m.sum() < min_cells or depth[m].max() < 0.2:
            continue
        in_dep |= m
        polys = _mask_to_polys(m, transform)
        if not polys:
            continue
        geom = unary_union(polys).simplify(cell / 2)
        dep_feats.append({"geom": geom, "props": {
            "area_m2": round(float(m.sum() * cell ** 2)), "max_depth_m": round(float(depth[m].max()), 2),
            "volume_m3": round(float(depth[m].sum() * cell ** 2)),
            # zlewnia zagłębienia: największa akumulacja D8 w jego obrębie (na powierzchni wypełnionej woda
            # z całej zlewni przechodzi przez zagłębienie) – z jakiej powierzchni spływa tu woda
            "catchment_ha": round(float(acc[m].max() * cell ** 2 / 1e4), 2),
            "touches_parcel": bool(geom.intersects(parcel_2180))}})
    near = parcel_2180.buffer(EDGE_MARGIN_M)
    dep_feats = [f for f in dep_feats if f["geom"].intersects(near)]
    dep_feats.sort(key=lambda f: (-int(f["props"]["touches_parcel"]), -f["props"]["volume_m3"]))
    dep_feats = dep_feats[:30]

    # linie spływu: komórki o zlewni ≥ 1 ha (min. 25 komórek)
    thr = max(25, int(10_000 / cell ** 2))
    segs = []
    rr, cc = np.where(acc >= thr)
    for r, c in zip(rr, cc):
        k = fd[r, c]
        if k < 0:
            continue
        dr, dc = T.NB[k]
        segs.append(LineString([(xs[c], ys[r]), (xs[c + dc], ys[r + dr])]))
    flow_feats = []
    if segs:
        merged = linemerge(unary_union(segs))
        lines = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
        for ln in lines:
            if ln.length < 3 * cell:
                continue
            # zlewnia na końcu linii
            ex, ey = ln.coords[-1]
            ci = min(ncols - 1, max(0, int(round((ex - x0) / cell))))
            ri = min(nrows - 1, max(0, int(round((y0 - ey) / cell))))
            flow_feats.append({"geom": ln.simplify(cell / 2), "props": {
                "length_m": round(ln.length), "catchment_ha": round(float(acc[ri, ci] * cell ** 2 / 1e4), 2),
                "crosses_parcel": bool(ln.intersects(parcel_2180))}})
        flow_feats = [f for f in flow_feats if f["geom"].intersects(near)]
        flow_feats.sort(key=lambda f: (-int(f["props"]["crosses_parcel"]), -f["props"]["catchment_ha"]))
        flow_feats = flow_feats[:40]

    exits = _runoff_exits(fd, acc, inside, xs, ys, cell, parcel_2180)

    zin = z[inside]
    t_in = float(tpi_r[inside].mean())
    dep_share = float((in_dep & inside).sum() / inside.sum())
    slope_in = slope[inside]
    pos, label = T.classify_position(t_in, float(np.std(tpi_r)), float(slope_in.mean()), dep_share)
    return {
        "elevation_mean_m": round(float(zin.mean()), 1), "elevation_min_m": round(float(zin.min()), 1),
        "elevation_max_m": round(float(zin.max()), 1), "slope_mean_deg": round(float(slope_in.mean()), 1),
        "slope_max_deg": round(float(np.percentile(slope_in, 98)), 1),
        "aspect_dominant": T.dominant_aspect(aspect, slope, inside), "position": pos,
        "position_label_pl": label, "tpi_m": round(t_in, 2), "twi_mean": round(float(twi[inside].mean()), 1),
        "_dep": dep_feats, "_flow": flow_feats, "_exits": exits, "_dep_share": dep_share, "_nan_share": nan_share,
        "_cells_in": int(inside.sum()),
    }


def _runoff_exits(fd: np.ndarray, acc: np.ndarray, inside: np.ndarray, xs: np.ndarray, ys: np.ndarray,
                  cell: float, parcel_2180: Any) -> list[dict]:
    """Odcinki granicy działki, przez które spływ powierzchniowy (D8) opuszcza pole.

    Komórka wyjścia = komórka w działce ze zlewnią ≥ 0,2 ha, której sąsiad „w dół” (D8) leży poza działką.
    Wokół punktu wyjścia bierzemy odcinek granicy ±max(20 m, krok siatki); sąsiednie odcinki łączymy.
    To tu pas buforowy / zadrzewienie zatrzyma najwięcej wody i gleby (zamiast „na całej granicy pola”).
    """
    from shapely.geometry import Point
    from shapely.ops import substring
    geom = max(parcel_2180.geoms, key=lambda g: g.area) if hasattr(parcel_2180, "geoms") else parcel_2180
    ring = LineString(geom.exterior.coords)
    thr = max(4, int(2_000 / cell ** 2))
    half = max(20.0, cell)
    pieces: list[tuple[Any, float]] = []
    nrows, ncols = fd.shape
    for r, c in zip(*np.where(inside & (acc >= thr))):
        k = fd[r, c]
        if k < 0:
            continue
        dr, dc = T.NB[k]
        r2, c2 = r + dr, c + dc
        if not (0 <= r2 < nrows and 0 <= c2 < ncols) or inside[r2, c2]:
            continue
        p = Point((xs[c] + xs[c2]) / 2, (ys[r] + ys[r2]) / 2)
        d = ring.project(p)
        seg = substring(ring, max(0.0, d - half), min(ring.length, d + half))
        pieces.append((seg, float(acc[r, c] * cell ** 2 / 1e4)))
    if not pieces:
        return []
    out = []
    merged = linemerge(unary_union([s for s, _ in pieces]))
    for ln in (list(merged.geoms) if hasattr(merged, "geoms") else [merged]):
        ha = max(a for s, a in pieces if s.distance(ln) < 1.0)
        out.append({"geom": ln, "props": {"catchment_ha": round(ha, 2), "length_m": round(ln.length)}})
    out.sort(key=lambda f: -f["props"]["catchment_ha"])
    return out[:8]


def _fc(feats: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": mapping(to_4326(f["geom"])), "properties": f["props"]} for f in feats]}


class TerrainConnector(Connector):
    key = "terrain"
    title = "Ukształtowanie terenu"
    category = "spatial"
    live_ttl_s = 30 * 24 * 3600
    timeout_s = 20
    cache_version = 4   # 4: odporne pobieranie NMT; 3: siatka wyrównana do wspólnej kratki + filtr brzegu okna

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        parcel = to_2180(shape(ctx.parcel.geometry.model_dump()))
        bounds, cell, nrows, ncols = snapped_grid(parcel.buffer(settings.analysis_buffer_m).bounds)
        z = await fetch_grid(bounds, cell, nrows, ncols)
        dem_src = "nmt"
        if np.isnan(z).mean() > 0.5:
            try:
                z = await fetch_grid_copdem(bounds, cell, nrows, ncols)
                dem_src = "copdem"
            except Exception as e:  # noqa: BLE001
                log.warning("Copernicus DEM fallback failed: %s", e)
        if np.isnan(z).mean() > 0.5:
            return self.block(BlockStatus.no_data, messages=["NMT nie zwrócił wysokości dla tego obszaru."],
                              provenance=[self.prov("GUGiK NMT", source_url="https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/", licence=LIC)])
        a = await asyncio.to_thread(analyse, z, cell, (bounds[0], bounds[3]), parcel)
        info = TerrainInfo(**{k: v for k, v in a.items() if not k.startswith("_")},
                           depressions_geojson=_fc(a["_dep"]), flow_lines_geojson=_fc(a["_flow"]),
                           runoff_exits_geojson=_fc(a["_exits"]),
                           dem_resolution_m=cell)
        n_dep = sum(1 for f in a["_dep"] if f["props"]["touches_parcel"])
        n_flow = sum(1 for f in a["_flow"] if f["props"]["crosses_parcel"])
        unc = [f"Wysokości z NMT GUGiK (skaning laserowy) próbkowane co {cell:.0f} m – drobne formy "
               f"(bruzdy, rowy węższe niż {cell:.0f} m) mogą być niewidoczne.",
               "Zagłębienia i linie spływu wyznaczone z samej rzeźby terenu – nie uwzględniają drenażu, "
               "przepustów ani rowów pod drogami.",
               f"Pokazujemy obiekty do {EDGE_MARGIN_M:.0f} m od działki (dalej wynik zależy od brzegu okna analizy): {n_dep} zagłębień bezodpływowych stykających się z działką, "
               f"{n_flow} głównych linii spływu przecinających działkę."]
        status = BlockStatus.ok
        if a["_nan_share"] > 0.05:
            status = BlockStatus.partial
            unc.append(f"Brak wysokości dla {a['_nan_share']:.0%} punktów – uzupełniono interpolacją.")
        if dem_src == "copdem":
            prov = self.prov("Copernicus DEM GLO-30 (ESA) – Microsoft Planetary Computer (zapasowo)",
                             source_url="https://planetarycomputer.microsoft.com/dataset/cop-dem-glo-30", licence=LIC_COPDEM,
                             notes=f"NMT GUGiK odmówił (przeciążenie / limit zapytań) – użyto DEM 30 m; siatka {nrows}×{ncols}")
            status = BlockStatus.partial
            unc.insert(0, "Usługa wysokości GUGiK była niedostępna – użyto zapasowego modelu Copernicus DEM (30 m, model "
                          "powierzchni z zabudową i lasem). Zagłębienia mniejsze niż ok. 1 ha i spadki mogą być niedokładne.")
        else:
            prov = self.prov("GUGiK – Numeryczny Model Terenu (NMT, ALS), usługa GetHByPointList",
                             source_url="https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/", licence=LIC,
                             notes=f"siatka {nrows}×{ncols}, krok {cell:.0f} m, bufor {settings.analysis_buffer_m:.0f} m")
        return self.block(status, info, provenance=[prov], uncertainty=unc)
