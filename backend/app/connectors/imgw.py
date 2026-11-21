"""IMGW-PIB – dobowe dane synoptyczne z najbliższej stacji (walidacja opadu z reanalizy).

Archiwum: https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop/
  - lata zakończone: `{rok}/{rok}_{kod3}_s.zip` (jedna stacja, ~11 KB),
  - rok bieżący: `{rok}/{rok}_{mm}_s.zip` (wszystkie stacje, jeden miesiąc).
CSV `s_d_*.csv` (cp1250): NSP, POST, ROK, MC, DZ, TMAX, WTMAX, TMIN, WTMIN, STD, WSTD, TMNG, WTMNG, SMDB, WSMDB…
Status „8” = brak pomiaru, „9” = brak zjawiska (opad 0). Katalog stacji ze współrzędnymi:
`data/imgw/synop_stations.json` (budowany raz: scripts/build_imgw_stations.py).
Licencja: dane publiczne IMGW-PIB – wymagane podanie źródła („Źródłem pochodzenia danych jest IMGW-PIB”).
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import zipfile
from datetime import date, timedelta
from functools import lru_cache
from statistics import mean
from typing import Any

from app.config import REPO_ROOT
from app.contracts.models import DailySeries
from app.core.cache import cache_get, cache_set, make_key
from app.core.http import get_with_retry

BASE = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop"
LIC = "Dane publiczne IMGW-PIB – „Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – PIB”"
MAX_DIST_KM = 60.0
_SEM: asyncio.Semaphore | None = None  # serwer IMGW dławi wiele równoległych pobrań


def _sem() -> asyncio.Semaphore:
    global _SEM
    if _SEM is None:
        _SEM = asyncio.Semaphore(3)
    return _SEM


@lru_cache
def stations() -> list[dict]:
    p = REPO_ROOT / "data" / "imgw" / "synop_stations.json"
    return json.loads(p.read_text(encoding="utf-8"))["stations"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_station(lat: float, lon: float) -> tuple[dict, float] | None:
    best = min(stations(), key=lambda s: haversine_km(lat, lon, s["lat"], s["lon"]), default=None)
    if not best:
        return None
    return best, haversine_km(lat, lon, best["lat"], best["lon"])


def parse_zip(content: bytes, station_code: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for name in zf.namelist():
            if not name.startswith("s_d_") or name.startswith("s_d_t_"):
                continue
            text = zf.read(name).decode("cp1250", errors="replace")
            for row in csv.reader(io.StringIO(text)):
                if len(row) < 15 or row[0].strip() != station_code:
                    continue
                d = f"{int(row[2]):04d}-{int(row[3]):02d}-{int(row[4]):02d}"
                status = row[14].strip()
                if status == "8":
                    out[d] = None
                elif status == "9":
                    out[d] = 0.0
                else:
                    try:
                        out[d] = float(row[13])
                    except ValueError:
                        out[d] = None
    return out


async def _fetch_zip(url: str, station_code: str, ttl: int) -> dict[str, float | None]:
    key = make_key("imgw_zip", url=url, st=station_code)
    if (hit := cache_get(key)) is not None:
        return hit
    async with _sem():
        r = await get_with_retry(url, timeout_s=5, attempts=1)
    data = parse_zip(r.content, station_code)
    cache_set(key, data, ttl)
    return data


async def station_precip(st: dict, start: date, end: date) -> dict[date, float | None]:
    today = date.today()
    urls = []
    for y in range(start.year, end.year + 1):
        if y < today.year:
            urls.append((f"{BASE}/{y}/{y}_{st['file_code']}_s.zip", 30 * 24 * 3600))
        else:
            for m in range(1, (end.month if y == end.year else 12) + 1):
                urls.append((f"{BASE}/{y}/{y}_{m:02d}_s.zip", 12 * 3600))
    res = await asyncio.gather(*(_fetch_zip(u, st["station_code"], ttl) for u, ttl in urls), return_exceptions=True)
    out: dict[date, float | None] = {}
    for r in res:
        if isinstance(r, dict):
            for k, v in r.items():
                d = date.fromisoformat(k)
                if start <= d <= end:
                    out[d] = v
    return out


def compare(series: DailySeries, st_precip: dict[date, float | None], end: date) -> dict[str, Any]:
    rean = dict(zip(series.dates, series.precip_mm))
    seasons = []
    for y in sorted({d.year for d in series.dates}):
        days = [date(y, 4, 1) + timedelta(days=i) for i in range(183)]
        pairs = [(rean.get(d), st_precip.get(d)) for d in days]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if len(pairs) >= 0.9 * len(days):
            seasons.append({"year": y, "reanalysis_mm": round(sum(a for a, _ in pairs), 0),
                            "station_mm": round(sum(b for _, b in pairs), 0)})
    last = [st_precip.get(end - timedelta(days=i)) for i in range(30)]
    last_ok = [x for x in last if x is not None]
    bias = None
    if seasons and sum(s["station_mm"] for s in seasons) > 0:
        bias = round(100 * (sum(s["reanalysis_mm"] for s in seasons) / sum(s["station_mm"] for s in seasons) - 1), 0)
    return {"seasons_apr_sep": seasons, "season_bias_pct": bias,
            "station_last_30d_precip_mm": round(sum(last_ok), 1) if len(last_ok) >= 27 else None,
            "mean_abs_season_diff_mm": round(mean(abs(s["reanalysis_mm"] - s["station_mm"]) for s in seasons), 0)
            if seasons else None}
