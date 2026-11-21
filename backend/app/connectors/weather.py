"""Meteo: 10 lat danych dobowych do daty analizy + prognoza.

Łańcuch dostawców (fallback), bo na hackathonie wszyscy dzielą jedno IP i Open-Meteo
szybko zwraca 429 „Daily API request limit exceeded” (zaobserwowane 21.11.2026):
  1) Open-Meteo Archive (ERA5/ERA5-Land, ~9–11 km, gotowe ET0 FAO) – CC BY 4.0, darmowe niekomercyjnie
  2) NASA POWER (MERRA-2, 0.5°×0.625°) – ET0 liczone u nas FAO-56 PM – domena publiczna
Dane NIE sięgają za as_of (brak „podglądania przyszłości” przy analizie historycznej).
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from app.config import settings
from app.connectors import imgw
from app.connectors.base import Connector, query_url
from app.contracts.models import (
    AnalysisContext,
    BlockStatus,
    DailySeries,
    DataBlock,
    WeatherForecast,
    WeatherHistory,
)
from app.core.http import RateLimited, get_with_retry
from app.science.et0 import et0_penman_monteith
from app.science.water_balance import monthly_climatology, season_summaries, window_vs_normal

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
NASA_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"


def history_range(as_of: date, years: int) -> tuple[date, date]:
    end = min(as_of, date.today() - timedelta(days=1))
    # od 1 stycznia: dzięki temu tabela sezonów IV–IX ma pełne 10 sezonów przed rokiem analizy
    start = date(end.year - years, 1, 1)
    return start, end


async def _open_meteo(lat: float, lon: float, start: date, end: date) -> tuple[DailySeries, dict]:
    params = {
        "latitude": lat, "longitude": lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration",
        "timezone": "Europe/Warsaw"}
    r = await get_with_retry(OPEN_METEO_ARCHIVE, params=params, timeout_s=10)
    j = r.json()
    d = j["daily"]
    s = DailySeries(dates=[date.fromisoformat(x) for x in d["time"]], precip_mm=d["precipitation_sum"],
                    tmax_c=d["temperature_2m_max"], tmin_c=d["temperature_2m_min"],
                    et0_mm=d["et0_fao_evapotranspiration"])
    return s, {"provider": "open-meteo-era5", "elevation": j.get("elevation"),
               "query_url": query_url(OPEN_METEO_ARCHIVE, params)}


async def _nasa_power(lat: float, lon: float, start: date, end: date) -> tuple[DailySeries, dict]:
    params = {
        "parameters": "PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN", "community": "AG",
        "longitude": lon, "latitude": lat, "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
        "format": "JSON"}
    r = await get_with_retry(NASA_POWER, params=params, timeout_s=15)
    j = r.json()
    prm = j["properties"]["parameter"]
    elev = (j.get("geometry", {}).get("coordinates") or [None, None, 100])[2] or 100
    fill = j.get("header", {}).get("fill_value", -999)
    clean = lambda v: None if v is None or v == fill or v <= -998 else float(v)
    dates, P, TX, TN, E = [], [], [], [], []
    for k in sorted(prm["PRECTOTCORR"].keys()):
        dd = date(int(k[:4]), int(k[4:6]), int(k[6:]))
        p, tx, tn = clean(prm["PRECTOTCORR"][k]), clean(prm["T2M_MAX"][k]), clean(prm["T2M_MIN"][k])
        rh, u2, rs = clean(prm["RH2M"][k]), clean(prm["WS2M"][k]), clean(prm["ALLSKY_SFC_SW_DWN"][k])
        e = (round(et0_penman_monteith(dd, lat, elev, tx, tn, rh, u2, rs), 2)
             if None not in (tx, tn, rh, u2, rs) else None)
        dates.append(dd); P.append(p); TX.append(tx); TN.append(tn); E.append(e)
    return DailySeries(dates=dates, precip_mm=P, tmax_c=TX, tmin_c=TN, et0_mm=E), \
        {"provider": "nasa-power", "elevation": elev, "query_url": query_url(NASA_POWER, params)}


async def _imgw_check(lat: float, lon: float, start: date, series: DailySeries) -> dict | None:
    ns = imgw.nearest_station(lat, lon)
    if not ns or ns[1] > imgw.MAX_DIST_KM:
        return None
    st, dist = ns
    pr = await imgw.station_precip(st, start, series.dates[-1])
    if not pr:
        return None
    out = imgw.compare(series, pr, series.dates[-1])
    out.update(station=st["name"], station_code=st["station_code"], distance_km=round(dist, 1))
    return out


class WeatherHistoryConnector(Connector):
    key = "weather_history"
    title = "Opady i parowanie – 10 lat"
    category = "meteo"
    live_ttl_s = 6 * 3600
    timeout_s = 20
    cache_version = 4

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        lon, lat = ctx.parcel.centroid
        start, end = history_range(ctx.as_of, settings.history_years)
        messages: list[str] = []
        series = meta = None
        provs = []
        used_fn = None
        for name, fn, page, lic in (
            ("Open-Meteo Historical Weather API (ERA5/ERA5-Land, ECMWF Copernicus)", _open_meteo,
             "https://open-meteo.com/en/docs/historical-weather-api", "CC BY 4.0 (dane), API darmowe do użytku niekomercyjnego"),
            ("NASA POWER (MERRA-2)", _nasa_power, "https://power.larc.nasa.gov/data-access-viewer/", "Domena publiczna (NASA)"),
        ):
            try:
                series, meta = await fn(lat, lon, start, end)
                note = ("Link „surowe dane” otwiera dokładnie to zapytanie (dane dobowe dla środka działki). "
                        "Sumy miesięczne, sezonowe, KBW i normy liczymy z tych danych sami.")
                if fn is _nasa_power:
                    note += " ET₀ nie pochodzi z NASA – liczymy je metodą FAO-56 Penman-Monteith z temperatury, wilgotności, wiatru i promieniowania."
                provs.append(self.prov(name, source_url=page, query_url=meta.get("query_url"), licence=lic,
                                       data_as_of=series.dates[-1], notes=note))
                used_fn = fn
                break
            except RateLimited:
                messages.append(f"{name}: limit zapytań (429) – przełączono na źródło zapasowe.")
            except Exception as e:  # noqa: BLE001
                messages.append(f"{name}: {type(e).__name__} – przełączono na źródło zapasowe.")
        if series is None:
            return self.block(BlockStatus.error, messages=messages,
                              uncertainty=["Brak danych meteorologicznych – ocena bilansu wodnego niemożliwa."])

        last30, last30n = window_vs_normal(series, end, 30, "precip_mm")
        p60, p60n = window_vs_normal(series, end, 60, "precip_mm")
        e60, e60n = window_vs_normal(series, end, 60, "et0_mm")
        grid = ("siatka ERA5-Land ok. 9–11 km" if meta["provider"] == "open-meteo-era5"
                else "siatka MERRA-2 ok. 50 km (zgrubna!)")
        data = WeatherHistory(
            provider=meta["provider"], grid_resolution_note=grid, start=start, end=series.dates[-1],
            daily=series, monthly_climatology=monthly_climatology(series), seasons=season_summaries(series),
            last_30d_precip_mm=last30, last_30d_precip_normal_mm=last30n,
            cwb_60d_mm=round(p60 - e60, 1) if p60 is not None and e60 is not None else None,
            cwb_60d_normal_mm=round(p60n - e60n, 1) if p60n is not None and e60n is not None else None,
        )
        unc = [f"Dane z reanalizy ({grid}), nie z pomiaru na działce – lokalne burze mogą być pominięte.",
               "Norma = średnia z dostępnych lat w oknie 10-letnim, nie klimatologia 30-letnia."]
        # walidacja: najbliższa stacja synoptyczna IMGW + (dla dat historycznych) sezony po dacie analizy
        async def _after() -> list:
            yesterday = date.today() - timedelta(days=1)
            if used_fn is None or end.year >= yesterday.year or yesterday < date(end.year, 9, 30):
                return []
            s2, _ = await used_fn(lat, lon, date(end.year, 4, 1), yesterday)
            have = {x.year for x in data.seasons}
            return [x for x in season_summaries(s2) if x.year not in have]
        chk, after = await asyncio.gather(asyncio.wait_for(_imgw_check(lat, lon, start, series), timeout=6),
                                          asyncio.wait_for(_after(), timeout=10), return_exceptions=True)
        if isinstance(chk, Exception):
            messages.append(f"IMGW (walidacja opadu): {type(chk).__name__}.")
        else:
            data.station_check = chk
        if isinstance(after, Exception):
            messages.append(f"Sezony po dacie analizy: {type(after).__name__}.")
        elif after:
            data.seasons_after_as_of = after
            unc.append(f"Sezony {after[0].year}–{after[-1].year} są PO dacie analizy – pokazane tylko do porównania, "
                       "nie wchodzą do oceny sytuacji na wybrany dzień.")
        if data.station_check:
            sc = data.station_check
            provs.append(self.prov(f"IMGW-PIB – dane dobowe stacji synoptycznej {sc['station']}",
                                   source_url=f"{imgw.BASE}/", licence=imgw.LIC,
                                   notes=f"{sc['distance_km']} km od działki; walidacja opadu reanalizy"))
            if sc.get("season_bias_pct") is not None and abs(sc["season_bias_pct"]) >= 15:
                unc.append(f"Opad z reanalizy różni się od pomiarów stacji IMGW {sc['station']} "
                           f"({sc['distance_km']} km) średnio o {sc['season_bias_pct']:+.0f}% w sezonach IV–IX – "
                           "traktuj sumy opadów ostrożnie.")
        status = BlockStatus.ok
        if (ctx.as_of - series.dates[-1]).days > 3:
            status = BlockStatus.partial
            unc.append(f"Najnowsze dane: {series.dates[-1].isoformat()} (opóźnienie reanalizy względem daty analizy).")
        return self.block(status, data, provenance=provs, uncertainty=unc, messages=messages)


class WeatherForecastConnector(Connector):
    key = "weather_forecast"
    title = "Prognoza pogody (16 dni)"
    category = "meteo"
    live_ttl_s = 3 * 3600

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        if ctx.as_of < date.today() - timedelta(days=1):
            return self.block(BlockStatus.not_applicable,
                              messages=["Analiza historyczna – prognoza nie dotyczy wybranej daty."])
        lon, lat = ctx.parcel.centroid
        params = {"latitude": lat, "longitude": lon, "forecast_days": 16, "timezone": "Europe/Warsaw",
                  "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration"}
        r = await get_with_retry(OPEN_METEO_FORECAST, params=params)
        d = r.json()["daily"]
        data = WeatherForecast(provider="open-meteo", dates=[date.fromisoformat(x) for x in d["time"]],
                               precip_mm=d["precipitation_sum"], et0_mm=d["et0_fao_evapotranspiration"],
                               tmax_c=d["temperature_2m_max"], tmin_c=d["temperature_2m_min"])
        return self.block(BlockStatus.ok, data,
                          provenance=[self.prov("Open-Meteo Forecast API", source_url="https://open-meteo.com/en/docs",
                                                query_url=query_url(OPEN_METEO_FORECAST, params),
                                                licence="CC BY 4.0")],
                          uncertainty=["Prognoza powyżej 5–7 dni ma niską sprawdzalność opadów."])
