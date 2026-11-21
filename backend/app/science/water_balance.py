"""Agregaty klimatycznego bilansu wodnego (KBW = P − ET0) liczone z serii dobowej.

Metoda nawiązuje do SMSR IUNG-PIB (KBW w okresach 60-dniowych w sezonie IV–IX,
Doroszewski i in. 2012). Progi suszy per uprawa/kategoria gleby → data/knowledge/crops/crops.yaml.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

from app.contracts.models import DailySeries, MonthlyClimate, SeasonSummary


def _sum(vals: list[float | None]) -> float | None:
    v = [x for x in vals if x is not None]
    return round(sum(v), 1) if v else None


def monthly_climatology(s: DailySeries) -> list[MonthlyClimate]:
    per_ym: dict[tuple[int, int], dict[str, list]] = defaultdict(lambda: {"p": [], "e": []})
    for d, p, e in zip(s.dates, s.precip_mm, s.et0_mm):
        per_ym[(d.year, d.month)]["p"].append(p)
        per_ym[(d.year, d.month)]["e"].append(e)
    per_m: dict[int, dict[str, list]] = defaultdict(lambda: {"p": [], "e": []})
    for (y, m), v in per_ym.items():
        if len(v["p"]) >= 25:  # tylko pełne miesiące
            if (ps := _sum(v["p"])) is not None:
                per_m[m]["p"].append(ps)
            if (es := _sum(v["e"])) is not None:
                per_m[m]["e"].append(es)
    out = []
    for m in range(1, 13):
        p = round(mean(per_m[m]["p"]), 1) if per_m[m]["p"] else None
        e = round(mean(per_m[m]["e"]), 1) if per_m[m]["e"] else None
        out.append(MonthlyClimate(month=m, precip_mean_mm=p, et0_mean_mm=e,
                                  cwb_mean_mm=round(p - e, 1) if p is not None and e is not None else None))
    return out


def _window_sum(s: DailySeries, end: date, days: int, field: str) -> float | None:
    start = end - timedelta(days=days - 1)
    vals = [v for d, v in zip(s.dates, getattr(s, field)) if start <= d <= end]
    return _sum(vals) if len(vals) >= days * 0.9 else None


def season_summaries(s: DailySeries) -> list[SeasonSummary]:
    years = sorted({d.year for d in s.dates})
    idx = {d: i for i, d in enumerate(s.dates)}
    out = []
    for y in years:
        season = [i for d, i in idx.items() if d.year == y and 4 <= d.month <= 9]
        if len(season) < 170:  # niepełny sezon
            continue
        p = _sum([s.precip_mm[i] for i in season])
        e = _sum([s.et0_mm[i] for i in season])
        run = best = 0
        for i in sorted(season):
            pr = s.precip_mm[i]
            run = run + 1 if pr is not None and pr < 1.0 else 0
            best = max(best, run)
        cwbs = []
        d = date(y, 5, 31)
        while d <= date(y, 9, 30):  # okna 60-dniowe co dekadę (jak SMSR)
            pp = _window_sum(s, d, 60, "precip_mm")
            ee = _window_sum(s, d, 60, "et0_mm")
            if pp is not None and ee is not None:
                cwbs.append(pp - ee)
            d += timedelta(days=10)
        out.append(SeasonSummary(year=y, precip_apr_sep_mm=p, et0_apr_sep_mm=e,
                                 cwb_apr_sep_mm=round(p - e, 1) if p is not None and e is not None else None,
                                 longest_dry_spell_days=best,
                                 min_cwb_60d_mm=round(min(cwbs), 1) if cwbs else None))
    return out


def window_vs_normal(s: DailySeries, as_of: date, days: int, field: str) -> tuple[float | None, float | None]:
    """Suma z `days` dni do as_of oraz średnia z tego samego okna w poprzednich latach."""
    cur = _window_sum(s, as_of, days, field)
    hist = []
    for k in range(1, 11):
        try:
            end = as_of.replace(year=as_of.year - k)
        except ValueError:  # 29 lutego
            end = as_of.replace(year=as_of.year - k, day=28)
        if (v := _window_sum(s, end, days, field)) is not None:
            hist.append(v)
    return cur, (round(mean(hist), 1) if hist else None)
