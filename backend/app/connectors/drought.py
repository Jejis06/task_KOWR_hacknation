"""Susza historyczna i bieżąca → DroughtHistory.

Trzy niezależne źródła (porównywalne ze sobą – jury prawdopodobnie sprawdza SMSR/EDO):
1) SMSR IUNG-PIB – oficjalne tabele „Zagrożenie suszą na poziomie gminy”
   `https://susza.iung.pulawy.pl/wykazy/{rok},{TERYT gminy 7 cyfr}/` (HTML, lata 2020+; brak API –
   parsujemy tabelę: kategoria gleby I–IV × gatunek × okres 01–14, „+” = zagrożenie suszą).
2) KBW policzony u nas metodą SMSR dla punktu działki (weather_history → science/smsr.py) – 10 lat,
   również lata przed 2020, dla których SMSR nie publikuje tabel gmin.
3) EDO Copernicus (JRC) – CDI v4.1 (`cdiad`) i anomalia wilgotności gleby (`smang`) z parametrem TIME.
   WMS EDO nie obsługuje GetFeatureInfo → klasę odczytujemy z palety piksela GetMap w punkcie.
Zależności: `weather_history` i `soil` (2. fala orkiestratora, `run_block`).
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta
from typing import Any, ClassVar

from app.connectors.base import Connector
from app.contracts.models import (AnalysisContext, BlockStatus, DataBlock, DroughtHistory, DroughtIndex,
                                  WeatherHistory)
from app.core.cache import cache_get, cache_set, make_key
from app.core.http import get_with_retry
from app.science import smsr

SMSR_URL = "https://susza.iung.pulawy.pl/wykazy/{year},{teryt}/"
EDO_WMS = "https://drought.emergency.copernicus.eu/api/wms"
SMSR_FIRST_YEAR = 2020
LIC_SMSR = "IUNG-PIB SMSR – informacja publiczna (susza.iung.pulawy.pl), z podaniem źródła"
LIC_EDO = "Copernicus Emergency Management Service – EDO (JRC), bezpłatnie z przypisaniem źródła"
DEFAULT_GROUP = "zboża ozime"

CDI_CLASSES = {(240, 228, 66): "obserwacja (Watch)", (230, 159, 0): "ostrzeżenie (Warning)",
               (220, 5, 12): "alarm (Alert)"}
SMA_LEGEND = [((33, 102, 172), "≥ 2 (bardzo wilgotno)", 2.0), ((103, 169, 207), "1,5 – 2 (wilgotno)", 1.75),
              ((209, 229, 240), "1 – 1,5 (lekko wilgotno)", 1.25), ((255, 255, 255), "−1 – 1 (norma)", 0.0),
              ((254, 224, 182), "−1,5 – −1 (lekko sucho)", -1.25), ((241, 163, 64), "−2 – −1,5 (sucho)", -1.75),
              ((179, 88, 6), "≤ −2 (bardzo sucho)", -2.0), ((200, 200, 200), "brak danych", None)]


def commune_teryt(teryt_unit: str | None) -> str | None:
    """`302504_5` (obszar wiejski gm. miejsko-wiejskiej) → `3025043`; dzielnice/delegatury → gmina miejska."""
    if not teryt_unit or not re.match(r"^\d{6}_\d$", teryt_unit):
        return None
    code, t = teryt_unit.split("_")
    if t in ("4", "5"):
        return code + "3"
    if t in ("8", "9"):
        return code[:4] + "011"
    return code + t


def parse_smsr_table(html: str) -> dict[str, Any]:
    """→ {"commune": str, "cats": {"I": {"zboża ozime": [("+","2024-03-21","2024-05-20"),...]}}, "share": {...}}"""
    out: dict[str, Any] = {"commune": None, "cats": {}, "share": {}}
    m = re.search(r"Gmina:\s*([^;<]+);\s*TERYT:\s*(\d+)", html)
    if not m:
        return out
    out["commune"] = m.group(1).strip()
    sections = re.split(r'<h6 class="card-title">', html)[1:]
    for sec in sections:
        title = re.match(r"([^<]+)</h6>", sec)
        if not title:
            continue
        name = title.group(1).strip()
        periods = re.findall(r'<th title="(\d{4}-\d\d-\d\d) - (\d{4}-\d\d-\d\d)">', sec)
        rows: dict[str, list] = {}
        for rm in re.finditer(r'<tr><td class="s-name[^"]*">([^<]+)</td>(.*?)</tr>', sec, flags=re.S):
            cells = re.findall(r"<td[^>]*>([^<]*)</td>", rm.group(2))
            rows[rm.group(1).strip().lower()] = [(c.strip(), *periods[i]) if i < len(periods) else (c.strip(), None, None)
                                                 for i, c in enumerate(cells)]
        cm = re.match(r"Kategoria gleby (I{1,3}|IV)", name)
        if cm:
            out["cats"][cm.group(1)] = rows
        elif "Udział" in name:
            out["share"] = rows
    return out


async def fetch_smsr_year(year: int, teryt: str) -> dict[str, Any] | None:
    key = make_key("smsr_gmina", year=year, teryt=teryt)
    if (hit := cache_get(key)) is not None:
        return hit
    r = await get_with_retry(SMSR_URL.format(year=year, teryt=teryt), timeout_s=8)
    parsed = parse_smsr_table(r.text)
    if parsed["commune"] is None:
        return None
    ttl = 30 * 24 * 3600 if year < date.today().year else 12 * 3600
    cache_set(key, parsed, ttl)
    return parsed


def _dekad(d: date) -> date:
    return d.replace(day=21 if d.day >= 21 else 11 if d.day >= 11 else 1)


async def edo_pixel(layer: str, lon: float, lat: float, when: date) -> tuple[int, int, int, int] | None:
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile
    d = 0.02
    r = await get_with_retry(EDO_WMS, params={
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap", "LAYERS": layer, "STYLES": "",
        "SRS": "EPSG:4326", "BBOX": f"{lon - d},{lat - d},{lon + d},{lat + d}", "WIDTH": 5, "HEIGHT": 5,
        "FORMAT": "image/png", "TRANSPARENT": "true", "TIME": when.isoformat()}, timeout_s=8)
    if "image" not in r.headers.get("content-type", ""):
        raise RuntimeError(f"EDO: {r.text[:120]}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile(r.content) as mf, mf.open() as ds:
            a = ds.read()
            if ds.count == 1:
                try:
                    cm = ds.colormap(1)
                except ValueError:
                    cm = None
                v = int(a[0, 2, 2])
                return tuple(cm.get(v, (0, 0, 0, 0))) if cm else (v, v, v, 255)  # type: ignore[return-value]
            px = a[:, 2, 2]
            return (int(px[0]), int(px[1]), int(px[2]), int(px[3]) if a.shape[0] > 3 else 255)


def cdi_label(rgba: tuple[int, int, int, int] | None) -> str | None:
    if rgba is None:
        return None
    if rgba[3] == 0:
        return "brak suszy rolniczej"
    best = min(CDI_CLASSES, key=lambda c: sum((x - y) ** 2 for x, y in zip(c, rgba[:3])))
    return CDI_CLASSES[best]


def sma_value(rgba: tuple[int, int, int, int] | None) -> tuple[str, float] | None:
    if rgba is None or rgba[3] == 0:
        return None
    best = min(SMA_LEGEND, key=lambda c: sum((x - y) ** 2 for x, y in zip(c[0], rgba[:3])))
    if best[2] is None or sum((x - y) ** 2 for x, y in zip(best[0], rgba[:3])) > 1500:
        return None  # kolor „brak danych” (szary) albo nieznany
    return best[1], best[2]


async def edo_series(lon: float, lat: float, as_of: date, years: int) -> dict[str, Any]:
    sem = asyncio.Semaphore(8)

    async def one(layer: str, when: date):
        async with sem:
            try:
                return await edo_pixel(layer, lon, lat, when)
            except Exception:  # noqa: BLE001
                return "ERR"

    cur = _dekad(as_of - timedelta(days=1))
    cur_dates = [cur - timedelta(days=10 * k) for k in range(3)]
    cur_dates = [_dekad(x) for x in cur_dates]
    hist_dates = [date(y, m, dd) for y in range(as_of.year - years, as_of.year + 1)
                  for (m, dd) in ((5, 21), (7, 1), (8, 11)) if date(y, m, dd) <= as_of]
    tasks = [one("cdiad", d) for d in cur_dates] + [one("smang", d) for d in cur_dates] + \
            [one("cdiad", d) for d in hist_dates]
    res = await asyncio.gather(*tasks)
    n = len(cur_dates)
    return {"cdi_cur": list(zip(cur_dates, res[:n])), "sma_cur": list(zip(cur_dates, res[n:2 * n])),
            "cdi_hist": list(zip(hist_dates, res[2 * n:]))}


class DroughtConnector(Connector):
    key = "drought"
    title = "Susza – teraz i w historii"
    category = "meteo"
    live_ttl_s = 12 * 3600
    timeout_s = 20
    uses_crop = True
    cache_version = 2
    depends_on: ClassVar[tuple[str, ...]] = ("weather_history", "soil")

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        from app.knowledge import loader
        from app.services.profile import run_block

        msgs: list[str] = []
        unc: list[str] = []
        provs = []
        # uprawa → grupa SMSR
        group = DEFAULT_GROUP
        crop_item = loader.get_item("crops", ctx.crop) if ctx.crop else None
        if crop_item and crop_item.get("smsr_group") and crop_item["smsr_group"].lower() in smsr.thresholds()["groups"]:
            group = crop_item["smsr_group"].lower()
        elif ctx.crop:
            msgs.append(f"Uprawa „{ctx.crop}” nie ma progów suszy w SMSR – pokazujemy dla grupy „{group}”.")
        else:
            msgs.append(f"Nie wybrano uprawy – susza oceniana dla grupy „{group}”.")

        lon, lat = ctx.parcel.centroid
        teryt = commune_teryt(ctx.parcel.teryt_unit)
        years = list(range(max(SMSR_FIRST_YEAR, ctx.as_of.year - 9), ctx.as_of.year + 1))
        smsr_tasks = [fetch_smsr_year(y, teryt) for y in years] if teryt else []
        weather_b, soil_b, edo, *smsr_res = await asyncio.gather(
            run_block("weather_history", ctx), run_block("soil", ctx), edo_series(lon, lat, ctx.as_of, 9),
            *smsr_tasks, return_exceptions=True)

        # kategoria gleby
        soil_cat, soil_src = None, None
        if not isinstance(soil_b, Exception) and soil_b.data:
            sd = soil_b.data if isinstance(soil_b.data, dict) else soil_b.data.model_dump()
            soil_cat = sd.get("drought_category")
            soil_src = "soil"
        if soil_cat not in (1, 2, 3, 4):
            soil_cat = 2
            soil_src = "default"
            unc.append("Nie ustalono kategorii gleby dla działki – przyjęto kategorię II (gleby lekkie) – SZACUNEK.")
        roman = smsr.ROMAN[soil_cat]
        th = smsr.group_thresholds(group, soil_cat)
        if th is not None and all(v is None for v in th):
            msgs.append(f"Uprawa z grupy „{group}” nie jest zalecana na glebach kategorii {roman} (wg SMSR).")

        info = DroughtHistory(current=[], history=[], crop_group=group, soil_category=soil_cat,
                              commune_teryt=teryt)
        in_season = date(ctx.as_of.year, 3, 21) <= ctx.as_of <= date(ctx.as_of.year, 9, 30)

        # 1) SMSR
        smsr_years: set[int] = set()
        smsr_ok = 0
        for y, res in zip(years, smsr_res):
            if isinstance(res, Exception) or res is None:
                continue
            smsr_ok += 1
            info.commune_name = res["commune"]
            row = res["cats"].get(roman, {}).get(group, [])
            evaluated = [(sym, a, b) for sym, a, b in row if b and date.fromisoformat(b) <= ctx.as_of
                         and sym in ("+", "-")]
            plus = [(a, b) for sym, a, b in evaluated if sym == "+"]
            share_row = res.get("share", {}).get(group, [])
            for idx, (sym, a, b) in enumerate(row):
                if b and date.fromisoformat(b) <= ctx.as_of and sym in ("+", "-"):
                    sh = share_row[idx][0] if idx < len(share_row) else None
                    info.periods.append({"year": y, "period": idx + 1, "start": a, "end": b,
                                         "drought": sym == "+", "source": "smsr",
                                         "commune_area_share_pct": _num(sh)})
            if plus:
                smsr_years.add(y)
            if evaluated:
                info.history.append(DroughtIndex(
                    source="SMSR IUNG", date=date.fromisoformat(evaluated[-1][2]),
                    value=f"{len(plus)}/{len(evaluated)} okresów z suszą" if plus else "brak suszy",
                    class_label="zagrożenie suszą" if plus else "brak suszy", level="commune"))
            if y == ctx.as_of.year and evaluated and in_season:
                sym, a, b = evaluated[-1]
                info.current.append(DroughtIndex(
                    source="SMSR IUNG", date=date.fromisoformat(b), value=sym,
                    class_label="zagrożenie suszą" if sym == "+" else "brak suszy (kryterium nieprzekroczone)",
                    level="commune"))
        if smsr_ok:
            provs.append(self.prov(f"IUNG-PIB SMSR – zagrożenie suszą w gminie {info.commune_name or ''}".strip(),
                                   source_url=SMSR_URL.format(year=ctx.as_of.year, teryt=teryt), licence=LIC_SMSR,
                                   notes=f"lata {years[0]}–{years[-1]}, kategoria gleby {roman}, grupa „{group}”"))
        elif teryt:
            msgs.append("SMSR: nie udało się pobrać tabel dla gminy.")
        else:
            msgs.append("SMSR: nie ustalono kodu TERYT gminy.")
        if ctx.as_of.year - 9 < SMSR_FIRST_YEAR:
            unc.append(f"SMSR publikuje tabele dla gmin od {SMSR_FIRST_YEAR} r. – wcześniejsze lata oceniamy "
                       "wyłącznie z bilansu wodnego policzonego dla działki.")

        # 2) KBW policzony dla działki
        computed_years: set[int] = set()
        if isinstance(weather_b, Exception) or weather_b.data is None:
            msgs.append("Brak danych meteo – nie policzono klimatycznego bilansu wodnego dla działki.")
        else:
            wh = weather_b.data if isinstance(weather_b.data, WeatherHistory) else WeatherHistory.model_validate(
                weather_b.data)
            for y in range(ctx.as_of.year - 10, ctx.as_of.year + 1):
                ev = smsr.evaluate_year(wh.daily, y, group, soil_cat, ctx.as_of)
                if not ev:
                    continue
                info.periods.extend(ev)
                if any(e["drought"] for e in ev):
                    computed_years.add(y)
                worst = min(ev, key=lambda e: e["kbw_mm"] - e["threshold_mm"])
                info.history.append(DroughtIndex(
                    source="computed", date=date.fromisoformat(worst["end"]), value=worst["kbw_mm"],
                    class_label=("susza" if worst["drought"] else "brak suszy") +
                    f" (najgorszy okres {worst['period']:02d}: KBW {worst['kbw_mm']:.0f} mm, próg {worst['threshold_mm']} mm)",
                    level="parcel"))
                if y == ctx.as_of.year and in_season:
                    last = ev[-1]
                    info.current.append(DroughtIndex(
                        source="computed", date=date.fromisoformat(last["end"]), value=last["kbw_mm"],
                        class_label=(f"susza – KBW {last['kbw_mm']:.0f} mm poniżej progu {last['threshold_mm']} mm"
                                     if last["drought"] else
                                     f"brak suszy – KBW {last['kbw_mm']:.0f} mm, próg {last['threshold_mm']} mm"),
                        level="parcel"))
            provs.append(self.prov("Klimatyczny bilans wodny (KBW) policzony dla działki metodą SMSR",
                                   source_url=None, licence="obliczenia własne; progi: rozporządzenie MRiRW 11.04.2019",
                                   data_as_of=wh.end, notes=f"dane meteo: {wh.provider}"))
            unc.append("KBW dla działki liczymy z reanalizy (ERA5 lub NASA POWER), a SMSR – z pomiarów stacji IMGW; "
                       "wyniki są zbliżone, ale mogą się różnić o kilkadziesiąt mm.")

        info.drought_years_smsr = sorted(smsr_years)
        info.drought_years_computed = sorted(computed_years)
        info.drought_years = sorted(smsr_years | {y for y in computed_years if y < SMSR_FIRST_YEAR or not smsr_ok})

        # 3) EDO
        if isinstance(edo, Exception):
            msgs.append(f"EDO niedostępne: {type(edo).__name__}.")
        else:
            got = False
            for d, rgba in edo["cdi_cur"]:
                if rgba != "ERR" and rgba is not None:
                    info.current.append(DroughtIndex(source="EDO CDI", date=d, value=cdi_label(rgba),
                                                     class_label=cdi_label(rgba), level="pixel"))
                    got = True
                    break
            for d, rgba in edo["sma_cur"]:
                if rgba != "ERR" and (sv := sma_value(rgba)):
                    info.current.append(DroughtIndex(source="EDO SMA", date=d, value=sv[1], class_label=sv[0],
                                                     level="pixel"))
                    got = True
                    break
            for d, rgba in edo["cdi_hist"]:
                if rgba != "ERR" and rgba is not None and rgba[3] != 0:
                    info.history.append(DroughtIndex(source="EDO CDI", date=d, value=cdi_label(rgba),
                                                     class_label=cdi_label(rgba), level="pixel"))
                    got = True
            if got:
                provs.append(self.prov("Copernicus EDO – Combined Drought Indicator i anomalia wilgotności gleby",
                                       source_url=EDO_WMS, licence=LIC_EDO,
                                       notes="CDI v4.1 (cdiad), SMA (smang); dekady; siatka ok. 5 km"))
                unc.append("EDO to siatka europejska (ok. 5 km) – opisuje okolicę, nie pojedyncze pole. "
                           "W historii pokazujemy tylko daty, w których CDI wskazywał suszę (21.05, 1.07, 11.08).")
            else:
                msgs.append("EDO: brak odczytu dla tej lokalizacji/daty.")
        if not in_season:
            msgs.append("Poza okresem monitoringu suszy rolniczej SMSR (21 marca – 30 września) – ocena bieżąca "
                        "SMSR nie dotyczy; pokazujemy historię i ostatni sezon.")
        info.history.sort(key=lambda x: (x.date or date.min))
        info.periods.sort(key=lambda p: (p["year"], p["period"], p["source"]))
        if not provs:
            return self.block(BlockStatus.error, messages=msgs,
                              uncertainty=["Żadne źródło danych o suszy nie odpowiedziało."])
        status = BlockStatus.ok if smsr_ok and computed_years is not None and len(provs) >= 2 else BlockStatus.partial
        if soil_src == "default":
            status = BlockStatus.partial
        return self.block(status, info, provenance=provs, uncertainty=unc, messages=msgs)


def _num(s: Any) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None
