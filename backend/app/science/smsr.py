"""Metoda SMSR (IUNG-PIB) na danych z działki: KBW w 14 okresach sześciodekadowych vs progi z rozporządzenia.

Progi: data/knowledge/crops/smsr_thresholds.yaml (generowane z raw/smsr_progi_www.txt).
KBW = Σ(P − ET0) w okresie. SMSR liczy ET0 metodą Penmana z danych stacji IMGW interpolowanych na siatkę;
my – z ERA5/NASA POWER (FAO-56 Penman-Monteith) w punkcie działki → wynik zbliżony, nie identyczny.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any

import yaml

from app.config import settings
from app.contracts.models import DailySeries

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


@lru_cache
def thresholds() -> dict[str, Any]:
    path = settings.knowledge_dir / "crops" / "smsr_thresholds.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def periods_for_year(year: int) -> list[tuple[int, date, date]]:
    """[(nr 1–14, początek, koniec)]"""
    out = []
    for i, p in enumerate(thresholds()["periods"], start=1):
        a, b = p.split("..")
        out.append((i, date(year, int(a[:2]), int(a[3:])), date(year, int(b[:2]), int(b[3:]))))
    return out


def group_thresholds(group: str, soil_cat: int) -> list[int | None] | None:
    g = thresholds()["groups"].get(group.lower())
    if not g:
        return None
    return g[ROMAN[soil_cat]]["values"]


def kbw_sum(series: DailySeries, start: date, end: date) -> float | None:
    n = (end - start).days + 1
    vals = [(p, e) for d, p, e in zip(series.dates, series.precip_mm, series.et0_mm)
            if start <= d <= end and p is not None and e is not None]
    if len(vals) < 0.9 * n:
        return None
    return round(sum(p - e for p, e in vals), 1)


def evaluate_year(series: DailySeries, year: int, group: str, soil_cat: int, as_of: date) -> list[dict]:
    """Ocena wszystkich okresów roku zakończonych ≤ as_of i ≤ końca serii."""
    th = group_thresholds(group, soil_cat)
    if th is None or not series.dates:
        return []
    last = min(as_of, series.dates[-1])
    out = []
    for nr, a, b in periods_for_year(year):
        if b > last:
            break
        t = th[nr - 1]
        if t is None:
            continue
        k = kbw_sum(series, a, b)
        if k is None:
            continue
        out.append({"year": year, "period": nr, "start": a.isoformat(), "end": b.isoformat(), "kbw_mm": k,
                    "threshold_mm": t, "drought": k < t, "source": "computed"})
    return out
