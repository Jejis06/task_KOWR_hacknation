"""Sentinel-2 L2A → VegetationInfo (NDVI, NDMI, 10 lat, bez konta).

Źródło: Microsoft Planetary Computer (bez klucza) – STAC `sentinel-2-l2a` + Data API (titiler)
`/api/data/v1/item/statistics`: statystyki wyrażenia pasm liczone PO STRONIE SERWERA dla geometrii działki
(odpowiedź = mały JSON, ~0,5 s/scenę). Dlaczego nie odczyt COG lokalnie (Earth Search / S3 us-west-2):
na łączu hackathonu kafel 1,5 MB pobierał się ~70 s (21.11.2026) – nie do przyjęcia.

Wyrażenia (maska chmur SCL: 4 = roślinność, 5 = gleba odkryta; korekta BOA −1000 od baseline 04.00):
  clear = (SCL==4)|(SCL==5)
  NDVI  = Σ clear·(B08−B04)/(B08+B04−2·off) / Σ clear     NDMI analogicznie z B11.
- latest: najnowsza scena ≤ as_of z ≥ 60% czystych pikseli (z ostatnich 60 dni).
- series: ≤ 1 czysta scena na miesiąc IV–X w każdym roku; wynik sceny cache'owany na stałe; gdy seria nie
  zmieści się w budżecie, zapytania kończą się w tle i trafiają do cache (status partial z komunikatem).
- baseline_same_doy: mediana NDVI z innych lat w oknie ±20 dni od dnia roku `latest`.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import time
from datetime import date, timedelta
from typing import Any

from app.connectors.base import Connector
from app.contracts.models import AnalysisContext, BlockStatus, DataBlock, VegetationInfo, VegetationObs
from app.core.cache import cache_get, cache_set, make_key
from app.core.http import RateLimited, get_client

log = logging.getLogger(__name__)
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_STATS = "https://planetarycomputer.microsoft.com/api/data/v1/item/statistics"
LIC = "Copernicus Sentinel data {year} (ESA) – bezpłatne, wymagane przypisanie; dane zmodyfikowane (NDVI/NDMI)"
SCENE_TTL_S = 365 * 24 * 3600
SERIES_BUDGET_S = 10.0
_SEM: asyncio.Semaphore | None = None


def _sem() -> asyncio.Semaphore:
    global _SEM
    if _SEM is None:
        _SEM = asyncio.Semaphore(10)
    return _SEM


async def stac_search(bbox: tuple[float, float, float, float], start: date, end: date, max_cloud: float,
                      limit: int = 250) -> list[dict]:
    body = {"collections": ["sentinel-2-l2a"], "bbox": list(bbox),
            "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z", "limit": limit,
            "query": {"eo:cloud_cover": {"lt": max_cloud}},
            "fields": {"include": ["id", "properties.datetime", "properties.eo:cloud_cover",
                                   "properties.s2:processing_baseline"], "exclude": ["assets", "links", "geometry"]}}
    last: Exception | None = None
    for attempt in range(2):
        try:
            r = await get_client().post(PC_STAC, json=body, timeout=10)
            if r.status_code == 429:
                raise RateLimited("Planetary Computer STAC 429")
            r.raise_for_status()
            return r.json().get("features", [])
        except RateLimited:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            await asyncio.sleep(0.5 * (attempt + 1))
    assert last is not None
    raise last


def boa_offset(item: dict) -> float:
    try:
        return 1000.0 if float(item["properties"].get("s2:processing_baseline") or 0) >= 4.0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def expressions(off: float, with_ndmi: bool) -> str:
    c = "((SCL==4)|(SCL==5))"
    ex = [f"{c}*1.0", f"{c}*(B08-B04)/(B08+B04-{2 * off:.1f})"]
    if with_ndmi:
        ex.append(f"{c}*(B08-B11)/(B08+B11-{2 * off:.1f})")
    return ";".join(ex)


def parse_stats(j: dict) -> dict[str, Any]:
    st = list(j.get("properties", {}).get("statistics", {}).values())
    if len(st) < 2:
        raise ValueError(f"PC statistics: nieoczekiwana odpowiedź {str(j)[:200]}")
    clear_n, total = st[0]["sum"], st[0]["count"] or 0
    out: dict[str, Any] = {"clear_frac": round(clear_n / total, 3) if total else 0.0, "n_px": int(total)}
    if clear_n >= max(3, 0.3 * total):
        out["ndvi"] = round(st[1]["sum"] / clear_n, 3)
        if len(st) > 2:
            out["ndmi"] = round(st[2]["sum"] / clear_n, 3)
    return out


async def scene_obs(item: dict, parcel_id: str, feature: dict, with_ndmi: bool) -> dict[str, Any] | None:
    key = make_key("s2pc", id=item["id"], parcel=parcel_id, ndmi=with_ndmi, v=1)
    if (hit := cache_get(key)) is not None:
        return hit
    params = {"collection": "sentinel-2-l2a", "item": item["id"], "asset_as_band": "true", "max_size": "1024",
              "expression": expressions(boa_offset(item), with_ndmi)}
    async with _sem():
        try:
            r = await get_client().post(PC_STATS, params=params, json=feature, timeout=15)
            if r.status_code == 429:
                return None
            r.raise_for_status()
            res = parse_stats(r.json())
        except Exception as e:  # noqa: BLE001
            log.warning("PC stats %s failed: %s", item["id"], e)
            return None
    res.update(id=item["id"], date=item["properties"]["datetime"][:10],
               cloud=item["properties"].get("eo:cloud_cover"))
    cache_set(key, res, SCENE_TTL_S)
    return res


def pick_monthly(items: list[dict], months: range = range(4, 11)) -> list[dict]:
    best: dict[tuple[int, int], dict] = {}
    for it in items:
        d = it["properties"]["datetime"][:10]
        y, m = int(d[:4]), int(d[5:7])
        if m not in months:
            continue
        k = (y, m)
        if k not in best or it["properties"]["eo:cloud_cover"] < best[k]["properties"]["eo:cloud_cover"]:
            best[k] = it
    return [best[k] for k in sorted(best)]


def baseline_same_doy(series: list[VegetationObs], ref: date, window_days: int = 20) -> float | None:
    vals = []
    for o in series:
        if o.date.year == ref.year or o.ndvi is None:
            continue
        try:
            same = o.date.replace(year=ref.year)
        except ValueError:
            continue
        if abs((same - ref).days) <= window_days:
            vals.append(o.ndvi)
    return round(statistics.median(vals), 3) if len(vals) >= 2 else None


class VegetationConnector(Connector):
    key = "vegetation"
    title = "Stan roślinności (satelita)"
    category = "satellite"
    live_ttl_s = 12 * 3600
    timeout_s = 22
    cache_version = 3

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        feature = {"type": "Feature", "properties": {}, "geometry": ctx.parcel.geometry.model_dump()}
        bbox = ctx.parcel.bbox
        pid = ctx.parcel.id
        as_of = ctx.as_of
        msgs: list[str] = []
        unc: list[str] = []
        in_season = 4 <= as_of.month <= 10
        t0 = time.perf_counter()

        y0 = as_of.year - 10
        searches = [stac_search(bbox, as_of - timedelta(days=60), as_of, 80, limit=40)]
        for y in range(y0, as_of.year + 1):
            end = min(date(y, 10, 31), as_of)
            if end >= date(y, 4, 1):
                searches.append(stac_search(bbox, date(y, 4, 1), end, 60))
        res = await asyncio.gather(*searches, return_exceptions=True)
        if all(isinstance(r, Exception) for r in res):
            return self.block(BlockStatus.error,
                              messages=[f"Planetary Computer STAC niedostępny: {type(res[0]).__name__}"],
                              uncertainty=["Brak danych satelitarnych – źródło nie odpowiedziało."])
        failed_years = sum(isinstance(r, Exception) for r in res[1:])
        if failed_years:
            msgs.append(f"Wyszukiwanie scen nie powiodło się dla {failed_years} sezonów.")
        recent = [] if isinstance(res[0], Exception) else res[0]
        season_items = [it for r in res[1:] if not isinstance(r, Exception) for it in r]

        # latest: od najnowszej, pierwsza czysta (max 6 kandydatów, równolegle)
        latest_obs: dict | None = None
        recent.sort(key=lambda it: it["properties"]["datetime"], reverse=True)
        cand = recent[:6]
        if cand:
            obs = await asyncio.gather(*(scene_obs(it, pid, feature, True) for it in cand))
            latest_obs = next((o for o in obs if o and o.get("ndvi") is not None and o["clear_frac"] >= 0.6), None)

        monthly = pick_monthly(season_items)
        tasks = [asyncio.ensure_future(scene_obs(it, pid, feature, False)) for it in monthly]
        remaining = max(2.0, SERIES_BUDGET_S - (time.perf_counter() - t0))
        done, pending = (await asyncio.wait(tasks, timeout=remaining)) if tasks else (set(), set())
        series = []
        for t in tasks:
            if t in done and (o := t.result()) and o.get("ndvi") is not None and o["clear_frac"] >= 0.7:
                series.append(VegetationObs(date=date.fromisoformat(o["date"]), ndvi=o["ndvi"],
                                            cloud_pct=o.get("cloud"), scene_id=o["id"]))
        series.sort(key=lambda s: s.date)

        info = VegetationInfo(series=series, in_growing_season=in_season)
        if latest_obs:
            lo = VegetationObs(date=date.fromisoformat(latest_obs["date"]), ndvi=latest_obs["ndvi"],
                               ndmi=latest_obs.get("ndmi"), cloud_pct=latest_obs.get("cloud"),
                               scene_id=latest_obs["id"])
            info.latest_age_days = (as_of - lo.date).days
            if in_season:
                info.latest = lo
                info.baseline_same_doy = baseline_same_doy(series, lo.date)
                if info.baseline_same_doy is not None:
                    info.anomaly = round(lo.ndvi - info.baseline_same_doy, 3)
            else:
                info.latest = lo  # informacyjnie; poza sezonem bez porównania z normą
                info.latest_age_days = (as_of - lo.date).days
        status = BlockStatus.ok
        if not in_season:
            status = BlockStatus.partial if series else BlockStatus.not_applicable
            msgs.append("Poza sezonem wegetacji (XI–III) bieżący NDVI nie opisuje stanu upraw (rośliny w spoczynku, "
                        "pole po zbiorze) – nie porównujemy go z normą; pokazujemy historię sezonów.")
        elif latest_obs is None:
            status = BlockStatus.partial
            msgs.append("Brak czystej (bezchmurnej) sceny Sentinel-2 w ostatnich 60 dniach przed datą analizy.")
        elif info.latest_age_days and info.latest_age_days > 20:
            unc.append(f"Najnowsze czyste zdjęcie ma {info.latest_age_days} dni – stan roślin mógł się zmienić.")
        if pending:
            if status == BlockStatus.ok:
                status = BlockStatus.partial
            msgs.append(f"Seria historyczna niekompletna ({len(done)}/{len(tasks)} scen) – pozostałe liczą się w tle; "
                        "ponowne zapytanie pokaże pełną serię.")
        first_year = min((s.date.year for s in series), default=None)
        if first_year is None or first_year > y0 + 1:
            unc.append("Archiwum Sentinel-2 L2A obejmuje Polskę w pełni od ok. 2017–2018 r. – dla wcześniejszych lat "
                       "NDVI może nie być.")
        unc += ["NDVI (wskaźnik zieleni roślin, 0–1) i NDMI (wskaźnik wilgotności liści) to średnia z czystych "
                "pikseli całej działki (10 m) – las, droga albo kilka upraw na działce uśredniają wynik.",
                "Chmury i cienie maskujemy klasyfikacją SCL z ESA; pojedyncze zakłócenia mogą zostać."]
        if info.anomaly is not None and info.anomaly < -0.1:
            unc.append("NDVI wyraźnie poniżej typowego dla tej pory roku – możliwa susza, ale też inny termin "
                       "siewu, zbiór albo inna uprawa niż w poprzednich latach.")
        newest = max([s.date for s in series] + ([info.latest.date] if info.latest else []), default=None)
        prov = self.prov("Copernicus Sentinel-2 L2A (ESA) – Microsoft Planetary Computer (STAC + Data API)",
                         source_url=PC_STATS, licence=LIC.format(year=as_of.year), data_as_of=newest,
                         notes=f"{len(series)} scen w serii (≤1/miesiąc IV–X); statystyki liczone dla granic działki")
        if not series and not info.latest:
            return self.block(BlockStatus.no_data if in_season else BlockStatus.not_applicable, info,
                              provenance=[prov], messages=msgs + ["Nie znaleziono czystych scen dla działki."],
                              uncertainty=unc)
        return self.block(status, info, provenance=[prov], uncertainty=unc, messages=msgs)
