"""Blok `analysis` (F2): ocena sytuacji wodnej → przyczyny → rekomendacje → nawadnianie.

Reguły jawne (nie LLM), liczone WYŁĄCZNIE z bloków danych pobranych dla działki i daty (bez danych z przyszłości –
bloki źródłowe już przestrzegają `as_of`). Każde stwierdzenie ma `evidence` z liczbą, jednostką i blokiem źródłowym.
Kolejność wymagana przez KOWR (Podstawy naukowe): ocena → przyczyny → retencja krajobrazowa → agrotechnika → nawadnianie.

Progi punktowe są autorskie (SZACUNEK) i opisane w `method` / `limitations`; oparte na:
- KBW i progach SMSR (blok drought – IUNG-PIB, rozp. MRiRW 11.04.2019),
- bilansie FAO-56 (ET₀ × Kc) dla nawadniania,
- katalogu NWRM (retention_measures.yaml) i zasadzie „zatrzymaj wodę tam, gdzie spadła”.
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta
from typing import Any, ClassVar

from app.connectors.base import Connector
from app.contracts.models import (
    AnalysisContext,
    AnalysisResult,
    BlockStatus,
    Cause,
    DataBlock,
    Evidence,
    FundingRef,
    IrrigationAdvice,
    Recommendation,
    SowingOption,
    WaterAssessment,
)
from app.knowledge import loader
from app.knowledge.blocks import FAO56_URL, _block_data, _knowledge_prov, doc_prov
from app.science import fao56

LEVELS = ["none", "low", "moderate", "high", "very_high"]
CURRENT_LABEL = {"none": "brak niedoboru wody", "low": "niewielki niedobór wody", "moderate": "umiarkowany niedobór wody",
                 "high": "duży niedobór wody", "very_high": "bardzo duży niedobór wody"}
HIST_LABEL = {"none": "bardzo niska podatność na suszę", "low": "niska podatność na suszę",
              "moderate": "umiarkowana podatność na suszę", "high": "wysoka podatność na suszę",
              "very_high": "bardzo wysoka podatność na suszę"}
CAUSE_LABEL = {"opady_deficyt": "Za mało opadów przy dużym parowaniu",
               "gleba_niska_retencja": "Gleba słabo zatrzymuje wodę",
               "odplyw_powierzchniowy": "Woda szybko odpływa z pola",
               "uprawa_wrazliwa": "Uprawa wrażliwa na niedobór wody"}
SENS = {"bardzo wysoka": 1.0, "wysoka": 0.7, "średnia": 0.4, "niska": 0.2}
SOIL_CAT_W = {1: 1.0, 2: 0.7, 3: 0.4, 4: 0.15}
NDMI_LOW = 0.05   # spadek NDMI względem normy uznawany za „niskie” (SZACUNEK zespołu)
MONTHS_PL = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]
DEPS = ("weather_history", "weather_forecast", "drought", "soil", "terrain", "hydrology", "vegetation",
        "land_cover", "protected_areas", "crop_calendar")
DEP_TITLES = {"weather_history": "opady i parowanie", "weather_forecast": "prognoza", "drought": "susza",
              "soil": "gleba", "terrain": "ukształtowanie terenu", "hydrology": "wody", "vegetation": "satelita (NDVI)",
              "land_cover": "użytkowanie terenu", "protected_areas": "obszary chronione",
              "crop_calendar": "kalendarz uprawy"}


def _mm(v: float | None, signed: bool = False) -> str:
    if v is None:
        return "brak danych"
    s = _pl_dec(f"{abs(v):.0f}")
    return (("+" if v > 0 else "−" if v < 0 else "") if signed else ("−" if v < 0 else "")) + s + " mm"


def _pl_dec(s: str) -> str:
    """Przecinek dziesiętny tylko między cyframi („0.6°” → „0,6°”), bez psucia „ok.” i końca zdania."""
    return re.sub(r"(?<=\d)\.(?=\d)", ",", s)


def _ev(text: str, block: str) -> Evidence:
    return Evidence(text=text, block=block)


MONTH_ABBR = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]


def _window(text: str, year: int) -> tuple[date, date]:
    a, b = text.split("..")
    return date(year, int(a[:2]), int(a[3:])), date(year, int(b[:2]), int(b[3:]))


def _dm(d: date) -> str:
    return f"{d.day} {MONTH_ABBR[d.month - 1]}"


def _cover_source(i: int | None) -> tuple[str | None, str | None]:
    src = loader.meta("cover_crops").get("sources") or []
    if i is None or i >= len(src):
        return None, None
    return src[i].get("title"), src[i].get("url")


def cover_crop_options(ctx: AnalysisContext, soil: dict | None, n: int = 3) -> list[SowingOption]:
    """Gatunki międzyplonu dobrane do uprawy głównej (termin zbioru, pokrewieństwo) i gleby; najbliższe okno siewu."""
    meta = loader.meta("cover_crops")
    crop = loader.get_item("crops", ctx.crop) if ctx.crop else None
    harvest = (crop or {}).get("harvest") or ""
    early_until = meta.get("early_harvest_until", "08-25")
    late = bool(".." in harvest and harvest.split("..")[0] > early_until)   # zbiór zaczyna się po terminie → tylko ozime
    cat = _soil_cat(soil)
    scored = []
    for it in loader.items("cover_crops"):
        if ctx.crop and ctx.crop in (it.get("avoid_after") or []):
            continue
        if late and it.get("type") == "ściernisk":
            continue
        if ".." in harvest and it["sow"].split("..")[1] < harvest.split("..")[0]:   # okno siewu kończy się przed zbiorem
            continue
        score = (2 if cat in (it.get("soils") or []) else 0) + (1 if it.get("status") == "OK" else 0)
        scored.append((score, it))
    scored.sort(key=lambda x: -x[0])
    out = []
    for _, it in scored[:n]:
        a, b = _window(it["sow"], ctx.as_of.year)
        if ctx.as_of > b:                                  # tegoroczne okno minęło → przyszły rok
            a, b = _window(it["sow"], ctx.as_of.year + 1)
        title, url = _cover_source(it.get("source"))
        kind = "międzyplon ścierniskowy – zaraz po zbiorze" if it.get("type") == "ściernisk" else "międzyplon ozimy"
        out.append(SowingOption(name=it["name_pl"], when=f"siew {_dm(a)} – {_dm(b)} {b.year} ({kind})",
                                why=it["why"], source_title=title, source_url=url))
    return out


def _funding_refs(ids: list[str]) -> list[FundingRef]:
    out = []
    for i in ids:
        it = loader.get_item("funding", i)
        if not it:
            continue
        url = next((u for u in (loader.public_source(x) for x in it.get("sources") or []) if u), None)
        out.append(FundingRef(name=it.get("name") or i, url=url))
    return out


def mulch_options() -> list[SowingOption]:
    out = []
    for it in loader.load("cover_crops").get("mulch") or []:
        title, url = _cover_source(it.get("source"))
        out.append(SowingOption(name=it["name_pl"], when=it["when"], why=it["why"], source_title=title, source_url=url))
    return out


def _seasons_pl(n: int) -> str:
    if n == 0:
        return "nie wystąpiła tu w żadnym sezonie"
    if n == 1:
        return "wystąpiła tu w 1 sezonie"
    return f"wystąpiła tu w {n} sezonach"


def _shift(level: str, k: int) -> str:
    return LEVELS[max(0, min(len(LEVELS) - 1, LEVELS.index(level) + k))]


def _soil_cat(soil: dict | None) -> int | None:
    if not soil:
        return None
    if soil.get("drought_category") in (1, 2, 3, 4):
        return int(soil["drought_category"])
    raw = str(soil.get("drought_susceptibility") or "").strip().upper()
    return {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}.get(raw)


def _drought_points(label: str | None) -> int:
    t = (label or "").lower()
    if not t or t.startswith("brak"):
        return 0
    if "susza" in t or "zagrożenie" in t or "alarm" in t:
        return 2
    if "ostrzeżenie" in t or "obserwacja" in t or "watch" in t or "warning" in t:
        return 1
    return 0


def _strict_protected(prot: dict | None) -> list[dict]:
    return [h for h in (prot or {}).get("hits") or []
            if any(k in (h.get("kind") or "").lower() for k in ("rezerwat", "park narodowy"))]


# ───────────────────────────── 1. ocena ─────────────────────────────
def assess(ctx: AnalysisContext, d: dict[str, dict | None]) -> WaterAssessment | None:
    w, dr, soil, veg, cal = d["weather_history"], d["drought"], d["soil"], d["vegetation"], d["crop_calendar"]
    if not w and not dr:
        return None  # bez meteo i bez SMSR nie oceniamy – mówimy to wprost
    ev: list[Evidence] = []
    pts = 0
    if w and w.get("cwb_60d_mm") is not None:
        cur, norm = w["cwb_60d_mm"], w.get("cwb_60d_normal_mm")
        diff = cur - norm if norm is not None else None
        if diff is not None:
            pts += 3 if diff < -60 else 2 if diff < -30 else 1 if diff < -10 else 0
            ev.append(_ev(f"KBW z 60 dni: {_mm(cur, True)} (zwykle {_mm(norm, True)}) – "
                          f"{'sucho o ' + _mm(-diff) if diff < 0 else 'wilgotniej o ' + _mm(diff)} względem normy",
                          "weather_history"))
    if w and w.get("last_30d_precip_mm") is not None:
        ev.append(_ev(f"opad z 30 dni: {_mm(w['last_30d_precip_mm'])} (norma {_mm(w.get('last_30d_precip_normal_mm'))})",
                      "weather_history"))
    if dr:
        best = max((dict(c) for c in dr.get("current") or []), key=lambda c: _drought_points(c.get("class_label")),
                   default=None)
        if best and _drought_points(best.get("class_label")):
            pts += _drought_points(best.get("class_label"))
            ev.append(_ev(f"{best.get('source')}: {best.get('class_label')}", "drought"))
    in_season = bool(cal and cal.get("in_season_on_as_of")) if cal and cal.get("crop") else \
        date(ctx.as_of.year, 4, 1) <= ctx.as_of <= date(ctx.as_of.year, 9, 30)
    if veg and veg.get("anomaly") is not None and veg.get("in_growing_season"):
        if veg["anomaly"] < -0.1:
            pts += 1
        ev.append(_ev(_pl_dec(f"NDVI {veg['anomaly']:+.2f} względem normy dla tej pory roku").replace("-", "−"), "vegetation"))
    # KBW (pogoda, siatka ~10 km) × NDMI (wilgotność liści z Sentinel-2, 20 m, ta działka): przyczyna vs skutek
    field_check = None
    ndmi_a = veg.get("ndmi_anomaly") if veg and veg.get("in_growing_season") else None
    kbw_diff = (w["cwb_60d_mm"] - w["cwb_60d_normal_mm"]) if w and w.get("cwb_60d_mm") is not None \
        and w.get("cwb_60d_normal_mm") is not None else None
    if ndmi_a is not None and kbw_diff is not None:
        kbw_dry, ndmi_low = kbw_diff < -30, ndmi_a < -NDMI_LOW
        case, label, text = {
            (True, True): ("confirmed", "Susza potwierdzona na polu",
                           "Pogoda była sucha i rośliny na tej działce faktycznie mają mniej wody w liściach niż zwykle."),
            (True, False): ("field_holds", "Pole lepiej trzyma wodę niż wskazuje pogoda",
                            "Mimo suchej pogody rośliny mają typową wilgotność liści – pomaga woda gruntowa, cięższa gleba "
                            "albo nawadnianie."),
            (False, True): ("local_problem", "Problem lokalny na polu",
                            "Pogoda była w normie, a rośliny mają mniej wody niż zwykle – przyczyna leży na polu (lekka "
                            "gleba, górka, drenaż, choroba). Warto obejrzeć pole."),
            (False, False): ("no_signal", "Brak sygnału suszy na polu",
                             "Ani pogoda, ani stan roślin nie wskazują na niedobór wody."),
        }[(kbw_dry, ndmi_low)]
        field_check = {"kbw": "dry" if kbw_dry else "normal", "ndmi": "low" if ndmi_low else "normal",
                       "kbw_anomaly_mm": round(kbw_diff, 1), "ndmi_anomaly": ndmi_a, "case": case,
                       "label_pl": label, "text": text}
        if case == "confirmed":
            pts += 1
        ev.append(_ev(_pl_dec(f"NDMI (woda w liściach) {ndmi_a:+.2f} względem normy – {label.lower()}")
                      .replace("-", "−"), "vegetation"))
    cur_level = "none" if pts == 0 else "low" if pts == 1 else "moderate" if pts <= 3 else "high" if pts == 4 else "very_high"
    if not in_season and LEVELS.index(cur_level) > LEVELS.index("moderate"):
        cur_level = "moderate"   # poza sezonem rośliny nie cierpią z braku wody – oceniamy zapas w glebie
    cur_summary = (f"Na {ctx.as_of.strftime('%d.%m.%Y')}: {CURRENT_LABEL[cur_level]}. " +
                   ("Uprawa jest w sezonie – niedobór wody może obniżać plon." if in_season and pts >= 2 else
                    "Poza sezonem wegetacji ocena dotyczy zapasu wody w glebie przed wiosną, a nie stresu roślin."
                    if not in_season else "Bieżący bilans wody nie odbiega wyraźnie od normy."))

    # okno = 10 ostatnich sezonów (z bieżącym); lata spoza okna nie są ani liczone, ani pokazywane
    years = sorted(y for y in set((dr or {}).get("drought_years") or []) if ctx.as_of.year - 10 < y <= ctx.as_of.year)
    n_years = len(years)
    hist = "low" if n_years == 0 else "moderate" if n_years <= 2 else "high" if n_years <= 4 else "very_high"
    cat = _soil_cat(soil)
    if cat == 1:
        hist = _shift(hist, 1)
    elif cat == 4:
        hist = _shift(hist, -1)
    if dr is not None:
        ev.append(_ev(("brak suszy rolniczej w 10 ostatnich sezonach" if n_years == 0 else f"susza rolnicza w {n_years} z 10 ostatnich sezonów")
                      + (f" ({', '.join(map(str, years[-6:]))})" if years else ""), "drought"))
    if cat:
        ev.append(_ev(f"gleba kategorii {['I', 'II', 'III', 'IV'][cat - 1]} wg SMSR "
                      f"({['bardzo podatna', 'podatna', 'średnio podatna', 'mało podatna'][cat - 1]} na suszę)", "soil"))
    seasons = (w or {}).get("seasons") or []
    worst = min((s for s in seasons if s.get("cwb_apr_sep_mm") is not None), key=lambda s: s["cwb_apr_sep_mm"], default=None)
    if worst:
        ev.append(_ev(f"najsuchszy sezon (kwi–wrz): {worst['year']}, KBW {_mm(worst['cwb_apr_sep_mm'], True)}", "weather_history"))

    # miesiące ryzyka: okresy suszy z bloku drought → najczęstsze miesiące; inaczej najbardziej ujemny KBW IV–IX
    months: dict[int, int] = {}
    for p in (dr or {}).get("periods") or []:
        if p.get("drought") and p.get("end"):
            m = date.fromisoformat(str(p["end"])[:10]).month
            months[m] = months.get(m, 0) + 1
    if months:
        crit = sorted(sorted(months, key=lambda m: -months[m])[:3])
    else:
        clim = [m for m in (w or {}).get("monthly_climatology") or [] if 4 <= m["month"] <= 9 and m.get("cwb_mean_mm") is not None]
        crit = sorted(m["month"] for m in sorted(clim, key=lambda m: m["cwb_mean_mm"])[:3])
    hist_summary = (f"W ostatnich 10 latach susza rolnicza {_seasons_pl(n_years)}. " +
                    (f"Największe ryzyko niedoboru wody: {', '.join(MONTHS_PL[m - 1] for m in crit)}." if crit else ""))

    have = sum(x is not None for x in (w, dr, soil, veg))
    conf = "high" if have == 4 else "medium" if have >= 2 else "low"
    if field_check and field_check["case"] == "confirmed" and conf == "medium":
        conf = "high"   # model pogodowy potwierdzony pomiarem z pola
    return WaterAssessment(current_level=cur_level, current_label_pl=CURRENT_LABEL[cur_level], current_summary=cur_summary,
                           historical_level=hist, historical_label_pl=HIST_LABEL[hist], historical_summary=hist_summary,
                           drought_years=years, critical_months=crit, confidence=conf, evidence=ev,
                           field_check=field_check)


# ───────────────────────────── 2. przyczyny ─────────────────────────────
def causes(ctx: AnalysisContext, d: dict[str, dict | None], field_check: dict | None = None) -> list[Cause]:
    w, soil, terr, hyd = d["weather_history"], d["soil"], d["terrain"], d["hydrology"]
    out: list[tuple[float, Cause]] = []
    seasons = [s["cwb_apr_sep_mm"] for s in (w or {}).get("seasons") or [] if s.get("cwb_apr_sep_mm") is not None]
    if seasons:
        mean = sum(seasons) / len(seasons)
        wt = max(0.0, min(1.0, -mean / 400))
        ev = [_ev(f"średni KBW kwiecień–wrzesień z {len(seasons)} lat: {_mm(mean, True)}", "weather_history")]
        longest = max((s.get("longest_dry_spell_days") or 0 for s in (w or {}).get("seasons") or []), default=0)
        if longest:
            ev.append(_ev(f"najdłuższy okres bez deszczu w sezonie: {longest} dni", "weather_history"))
        out.append((wt, Cause(key="opady_deficyt", label_pl=CAUSE_LABEL["opady_deficyt"],
                              explanation="W sezonie wegetacyjnym parowanie przewyższa opady – roślinom brakuje wody nawet przy przeciętnej pogodzie."
                              if mean < -150 else "Bilans opadów i parowania jest tylko lekko ujemny – susze zależą od konkretnego roku.",
                              evidence=ev)))
    cat = _soil_cat(soil)
    if soil and (cat or soil.get("awc_mm") is not None):
        wt = SOIL_CAT_W.get(cat or 3, 0.4)
        ev = []
        if cat:
            ev.append(_ev(f"kategoria gleby SMSR {['I', 'II', 'III', 'IV'][cat - 1]}", "soil"))
        if soil.get("awc_mm") is not None:
            ev.append(_ev(f"zapas wody dostępnej dla roślin ok. {soil['awc_mm']:.0f} mm w 1 m gleby (szacunek)", "soil"))
            if soil["awc_mm"] < 120:
                wt = min(1.0, wt + 0.15)
        if soil.get("soc_g_kg") is not None:
            ev.append(_ev(f"węgiel organiczny {soil['soc_g_kg']:.0f} g/kg", "soil"))
            if soil["soc_g_kg"] < 10:
                wt = min(1.0, wt + 0.1)
        if field_check and field_check.get("case") == "local_problem":
            wt = min(1.0, wt + 0.25)
            ev.append(_ev("pogoda w normie, a NDMI roślin niższe niż zwykle – przyczyna na polu, nie w pogodzie", "vegetation"))
        out.append((wt, Cause(key="gleba_niska_retencja", label_pl=CAUSE_LABEL["gleba_niska_retencja"],
                              explanation="Gleba lekka lub uboga w próchnicę szybko przesycha; więcej materii organicznej zwiększa zapas wody."
                              if wt >= 0.6 else "Gleba ma przeciętną zdolność zatrzymywania wody.", evidence=ev)))
    wt, ev = 0.0, []
    if terr:
        slope = terr.get("slope_mean_deg")
        if slope is not None:
            ev.append(_ev(_pl_dec(f"średni spadek działki {slope:.1f}°"), "terrain"))
            wt += 0.6 if slope > 3 else 0.3 if slope > 1.5 else 0.0
        if terr.get("position") in ("hilltop", "upper_slope"):
            wt += 0.3
            ev.append(_ev(f"położenie: {terr.get('position_label_pl') or terr['position']}", "terrain"))
        flows = [f for f in ((terr.get("flow_lines_geojson") or {}).get("features") or [])
                 if (f.get("properties") or {}).get("crosses_parcel")]
        if flows:
            wt += 0.25
            ev.append(_ev(f"{len(flows)} linii spływu wody przecina działkę", "terrain"))
    ditches = sorted([x for x in (hyd or {}).get("nearest_water") or [] if x.get("kind") == "ditch"],
                     key=lambda x: x["distance_m"])
    if ditches and ditches[0]["distance_m"] <= 300:
        wt += 0.2
        ev.append(_ev(f"rów melioracyjny {ditches[0]['distance_m']:.0f} m od działki odprowadza wodę", "hydrology"))
    if ev and wt > 0:
        out.append((min(1.0, wt), Cause(key="odplyw_powierzchniowy", label_pl=CAUSE_LABEL["odplyw_powierzchniowy"],
                                        explanation="Woda z deszczu i roztopów spływa po powierzchni lub rowami, zamiast wsiąkać w glebę.",
                                        evidence=ev)))
    crop = loader.get_item("crops", ctx.crop) if ctx.crop else None
    if crop and crop.get("drought_sensitivity") in SENS:
        out.append((SENS[crop["drought_sensitivity"]], Cause(
            key="uprawa_wrazliwa", label_pl=CAUSE_LABEL["uprawa_wrazliwa"],
            explanation=f"{crop['name_pl']}: wrażliwość na suszę {crop['drought_sensitivity']}; okresy krytyczne: "
                        f"{'; '.join(crop.get('critical') or [])}.",
            evidence=[_ev(f"{crop['name_pl']} – wrażliwość na niedobór wody: {crop['drought_sensitivity']}", "crop_calendar")])))
    out = [(wt, c) for wt, c in out if wt >= 0.15]
    total = sum(wt for wt, _ in out) or 1.0
    for wt, c in out:
        c.share = round(wt / total, 2)
    return [c for _, c in sorted(out, key=lambda x: -x[0])]


# ───────────────────────────── bilans ilościowy działki ─────────────────────────────
def _weir_point(ctx: AnalysisContext, ditch: dict) -> dict | None:
    """Proponowane miejsce zastawki: punkt rowu najbliższy działce (EPSG:4326; orientacyjnie – do sprawdzenia w terenie)."""
    from shapely.geometry import mapping, shape
    from shapely.ops import nearest_points
    try:
        g = ditch.get("geometry")
        if not g:
            return None
        pt = nearest_points(shape(ctx.parcel.geometry.model_dump()), shape(g))[1]
        return {"type": "Feature", "geometry": mapping(pt), "properties": {"kind": "weir"}}
    except Exception:  # noqa: BLE001 – brak geometrii to nie błąd analizy
        return None


COARSE_DEM_M = 25.0          # DEM rzadszy niż to = model zgrubny (Copernicus 30 m)
COARSE_MIN_AREA_HA = 3.0     # poniżej tej powierzchni zagłębienia z modelu 30 m są niewiarygodne


def _coarse_terrain(ctx: AnalysisContext, terr: dict | None) -> bool:
    """Rzeźba z modelu ~30 m na małej działce: kilka komórek siatki – zagłębień i miejsc odpływu nie oceniamy."""
    res = (terr or {}).get("dem_resolution_m")
    return bool(res and res >= COARSE_DEM_M and (ctx.parcel.area_ha or 0) < COARSE_MIN_AREA_HA)


def _best_depression(terr: dict | None) -> dict | None:
    deps = [f for f in ((terr or {}).get("depressions_geojson") or {}).get("features") or []
            if (f.get("properties") or {}).get("touches_parcel")]
    return max(deps, key=lambda f: (f.get("properties") or {}).get("volume_m3") or 0) if deps else None


def water_balance(ctx: AnalysisContext, d: dict[str, dict | None]) -> dict | None:
    """Deficyt wody w mm (KBW) przeliczony na m³ dla działki + pojemność i zlewnia zagłębienia.

    1 mm na 1 ha = 10 m³. Napływ do zagłębienia = nadwyżka KBW w półroczu chłodnym (X–III, średnia z 10 lat)
    × powierzchnia zlewni (D8) – to GÓRNY szacunek (część wody wsiąknie lub wyparuje po drodze).
    """
    w, terr = d["weather_history"], d["terrain"]
    if not w:
        return None
    area = ctx.parcel.area_ha
    seasons = [s["cwb_apr_sep_mm"] for s in w.get("seasons") or [] if s.get("cwb_apr_sep_mm") is not None]
    mean_def = max(0.0, -sum(seasons) / len(seasons)) if seasons else None
    worst = min(seasons) if seasons else None
    cur = w.get("cwb_60d_mm")
    out: dict[str, Any] = {
        "area_ha": round(area, 2),
        "deficit_60d_mm": round(max(0.0, -cur), 1) if cur is not None else None,
        "season_deficit_mm": round(mean_def, 1) if mean_def is not None else None,
        "worst_season_deficit_mm": round(max(0.0, -worst), 1) if worst is not None else None,
    }
    for k in ("deficit_60d", "season_deficit", "worst_season_deficit"):
        mm = out[f"{k}_mm"]
        out[f"{k}_m3"] = round(mm * area * 10) if mm is not None else None
    best = _best_depression(terr)
    if best:
        p = best.get("properties") or {}
        vol, catch = p.get("volume_m3") or 0, p.get("catchment_ha")
        winter = sum(m["cwb_mean_mm"] for m in w.get("monthly_climatology") or []
                     if m.get("cwb_mean_mm") is not None and (m["month"] >= 10 or m["month"] <= 3) and m["cwb_mean_mm"] > 0)
        inflow = round(winter * catch * 10) if catch is not None else None
        out.update(depression_volume_m3=vol, depression_area_m2=p.get("area_m2"), depression_catchment_ha=catch,
                   winter_surplus_mm=round(winter, 1), depression_inflow_m3=inflow,
                   depression_fill_pct=round(min(100.0, inflow / vol * 100)) if inflow is not None and vol else None,
                   coverage_season_pct=round(vol / out["season_deficit_m3"] * 100, 1)
                   if out.get("season_deficit_m3") else None)
    return out


# ───────────────────────────── 3–4. rekomendacje ─────────────────────────────
def recommendations(ctx: AnalysisContext, d: dict[str, dict | None], cs: list[Cause],
                    wb: dict | None = None) -> list[Recommendation]:
    terr, hyd, prot, soil, lc = d["terrain"], d["hydrology"], d["protected_areas"], d["soil"], d["land_cover"]
    measures = {m["id"]: m for m in loader.items("measures")}
    share = {c.key: c.share or 0 for c in cs}
    strict = _strict_protected(prot)
    crop = loader.get_item("crops", ctx.crop) if ctx.crop else None
    perennial = bool(crop and crop.get("type") == "wieloletnia")
    recs: list[Recommendation] = []

    def add(mid: str, title: str, why: str, ev: list[Evidence], when: str | None = None, where: dict | None = None,
            sowing: list[SowingOption] | None = None):
        m = measures[mid]
        recs.append(Recommendation(measure_id=mid, group=m["group"], title=title, why=why, when=when or m.get("when"),
                                   addresses=list(m.get("addresses") or []), legal_ids=list(m.get("legal_ids") or []),
                                   funding_ids=list(m.get("funding") or []), where_geojson=where, evidence=ev,
                                   sowing=sowing or [], funding=_funding_refs(m.get("funding") or [])))

    # retencja krajobrazowa – nie w parku narodowym / rezerwacie (budowa urządzeń praktycznie wykluczona)
    if not strict:
        ditches = sorted([x for x in (hyd or {}).get("nearest_water") or [] if x.get("kind") == "ditch"],
                         key=lambda x: x["distance_m"])
        if ditches and ditches[0]["distance_m"] <= 300:
            dch = ditches[0]
            nm = dch.get("name")
            nm = nm if nm and "rów" not in nm.lower() else "melioracyjnym"
            add("zastawka_row", f"Zastawka na rowie {nm}",
                f"Rów {dch['distance_m']:.0f} m od działki odprowadza wodę poza gospodarstwo. Piętrzenie (zastawka) wiosną "
                "zatrzyma wodę z roztopów w okolicy i podniesie poziom wód gruntowych.",
                [_ev(f"rów melioracyjny: {dch['distance_m']:.0f} m od działki", "hydrology")], when="przed roztopami (lut–mar)",
                where=_weir_point(ctx, dch))
        flood = (hyd or {}).get("in_flood_zone") or (hyd or {}).get("in_flood_hazard_area")
        deps = [f for f in ((terr or {}).get("depressions_geojson") or {}).get("features") or []
                if (f.get("properties") or {}).get("touches_parcel")]
        if _coarse_terrain(ctx, terr):
            deps = []
        if deps and not flood:
            best = _best_depression(terr) or max(deps, key=lambda f: (f.get("properties") or {}).get("volume_m3") or 0)
            p = best.get("properties") or {}
            wb = wb or {}
            ev = [_ev(f"zagłębienie bezodpływowe {p.get('area_m2', 0):.0f} m², głębokość do {p.get('max_depth_m', 0):.1f} m, "
                      f"pojemność ok. {p.get('volume_m3', 0):.0f} m³", "terrain"),
                  _ev("poza strefą zagrożenia powodziowego" if hyd and hyd.get("flood_zone_checked") else
                      "strefy powodziowej nie sprawdzono", "hydrology")]
            why = (f"Na działce jest naturalne zagłębienie (ok. {p.get('area_m2', 0):.0f} m², do {p.get('max_depth_m', 0):.1f} m), "
                   "w którym zbiera się woda – mniej kopania. Do 5000 m² i 3 m głębokości wystarczy zgłoszenie wodnoprawne.").replace(".0 m", " m")
            if wb.get("depression_catchment_ha") is not None:
                ev.append(_ev(_pl_dec(f"zlewnia zagłębienia (spływ D8): {wb['depression_catchment_ha']:.1f} ha"), "terrain"))
            if wb.get("depression_inflow_m3") is not None:
                ev.append(_ev(f"napływ w półroczu chłodnym ok. {wb['depression_inflow_m3']:.0f} m³ (nadwyżka KBW paź–mar "
                              f"{wb['winter_surplus_mm']:.0f} mm × zlewnia; górny szacunek)", "weather_history"))
                fill = wb.get("depression_fill_pct")
                if fill is not None and fill < 50:
                    why += (f" Uwaga: zlewnia jest mała – zimą spłynie tu ok. {wb['depression_inflow_m3']:.0f} m³, czyli ~{fill:.0f}% "
                            "pojemności; bez dodatkowego doprowadzenia wody oczko może być płytkie lub okresowo suche.")
                elif fill is not None:
                    why += f" Zlewnia wystarcza, by zimą napełnić zagłębienie (napływ ok. {wb['depression_inflow_m3']:.0f} m³)."
            if wb.get("coverage_season_pct") is not None and wb.get("season_deficit_m3"):
                ev.append(_ev(_pl_dec(f"pojemność pokrywa ok. {wb['coverage_season_pct']:.0f}% średniego niedoboru wody w sezonie "
                              f"({wb['season_deficit_m3']:.0f} m³ na całą działkę)"), "weather_history"))
            add("oczko_zbiornik", "Oczko wodne lub mały zbiornik w zagłębieniu terenu", why, ev,
                when="poza sezonem (paź–mar), po zgłoszeniu wodnoprawnym", where=best)
        slope = (terr or {}).get("slope_mean_deg")
        near_water = [x for x in (hyd or {}).get("nearest_water") or [] if x["distance_m"] <= 100 and x.get("kind") != "ditch"]
        exits = [] if _coarse_terrain(ctx, terr) else \
            [f for f in ((terr or {}).get("runoff_exits_geojson") or {}).get("features") or []]
        if share.get("odplyw_powierzchniowy", 0) >= 0.25 or (slope is not None and slope > 2) or near_water or exits:
            ev = []
            if slope is not None:
                ev.append(_ev(_pl_dec(f"średni spadek {slope:.1f}°"), "terrain"))
            if near_water:
                ev.append(_ev(f"{near_water[0].get('name') or 'ciek'} {near_water[0]['distance_m']:.0f} m od działki", "hydrology"))
            if exits:
                total_len = sum((f.get("properties") or {}).get("length_m") or 0 for f in exits)
                top = max((f.get("properties") or {}).get("catchment_ha") or 0 for f in exits)
                ev.append(_ev(_pl_dec(f"woda spływa z pola w {len(exits)} miejscach granicy (łącznie ok. {total_len:.0f} m); "
                              f"największy spływ zbiera wodę z {top:.1f} ha"), "terrain"))
                why = (f"Woda ucieka z pola w {len(exits)} konkretnych miejscach granicy (zaznaczone na mapie). Pas traw, krzewów "
                       f"lub drzew właśnie tam – łącznie ok. {total_len:.0f} m zamiast całego obwodu – spowolni odpływ, zatrzyma "
                       "glebę i ograniczy wysuszanie przez wiatr.")
                where = {"type": "FeatureCollection", "features": exits}
            else:
                why = "Pas traw, krzewów lub drzew w poprzek spływu spowalnia odpływ, zatrzymuje glebę i ogranicza wysuszanie przez wiatr."
                where = None
            add("pas_buforowy", "Pas zieleni lub zadrzewienie tam, gdzie woda ucieka z pola" if exits
                else "Pas zieleni lub zadrzewienie na granicy pola", why, ev, when="jesień lub wczesna wiosna", where=where)
        grass = (lc or {}).get("classes", {})
        is_grass = ctx.crop == "tuz" or (grass and max(grass, key=grass.get, default="").lower().startswith(("traw", "łąk")))
        wet = (terr or {}).get("position") in ("valley", "depression") or (hyd or {}).get("in_groundwater_flood_area")
        if is_grass and wet:
            add("mokradlo", "Podniesienie poziomu wody na łące (ekoschemat TUZ)",
                "Łąka w obniżeniu terenu to dobre miejsce na okresowe zatrzymanie wody – można za to dostać płatność ekoschematu.",
                [_ev(f"położenie: {(terr or {}).get('position_label_pl') or 'obniżenie'}", "terrain")])

    # agrotechnika – dobierana do przyczyn
    g = share.get("gleba_niska_retencja", 0)
    o = share.get("odplyw_powierzchniowy", 0)
    soc = (soil or {}).get("soc_g_kg")
    if not perennial:
        add("miedzyplony", "Międzyplon po zbiorze plonu głównego",
            "Okrywa roślinna po żniwach ogranicza parowanie i erozję, a po przyoraniu zwiększa próchnicę i zapas wody w glebie.",
            [_ev(f"węgiel organiczny {soc:.0f} g/kg", "soil")] if soc is not None else [], when="zaraz po zbiorze plonu głównego",
            sowing=cover_crop_options(ctx, soil))
    if g >= 0.2 or not perennial:
        ev = [_ev(f"udział przyczyny „gleba słabo zatrzymuje wodę”: {g:.0%}", "soil")] if g else []
        sav = _mulch_saving(ctx, d)
        if sav:
            ev.append(_ev(f"faza początkowa ({sav['days']} dni): parowanie z gleby ok. {sav['evap_mm']:.0f} mm; mulcz na 50% "
                          f"powierzchni oszczędza ok. {sav['saving_mm']:.0f} mm = {sav['saving_m3']:.0f} m³ na działce "
                          "(FAO-56: −5% parowania na każde 10% okrycia)", "crop_calendar"))
        add("resztki_mulcz", "Zostaw resztki pożniwne jako mulcz",
            "Mulcz na powierzchni zmniejsza parowanie z wierzchniej warstwy gleby w okresie najczęstszych susz.",
            ev, when="po zbiorze", sowing=mulch_options())
    if (soc is not None and soc < 15) or _soil_cat(soil) in (1, 2):
        add("materia_organiczna", "Zwiększ materię organiczną (obornik, kompost)",
            "Każdy wzrost próchnicy zwiększa pojemność wodną gleby (inicjatywa „4 promile”).",
            [_ev(f"węgiel organiczny {soc:.0f} g/kg", "soil")] if soc is not None else
            [_ev(f"gleba kategorii {_soil_cat(soil)} wg SMSR", "soil")])
    if (g >= 0.3 or o >= 0.3) and not perennial:
        add("uprawa_uproszczona", "Uprawa uproszczona zamiast orki",
            "Mniej przesychania wierzchniej warstwy i lepsza struktura gleby – woda łatwiej wsiąka.",
            [_ev(f"udział przyczyn glebowych i odpływu: {g + o:.0%}", "soil")])
    slope = (terr or {}).get("slope_mean_deg")
    if slope is not None and slope > 3 and not perennial:
        add("uprawa_w_poprzek_stoku", "Uprawa w poprzek stoku",
            "Bruzdy w poprzek spadku zatrzymują wodę deszczową na polu i ograniczają erozję.",
            [_ev(_pl_dec(f"średni spadek {slope:.1f}°"), "terrain")])

    # priorytet = suma udziałów przyczyn, na które działa rekomendacja (w obrębie grupy)
    for grp in ("retencja_krajobrazowa", "agrotechnika"):
        items = [r for r in recs if r.group == grp]
        items.sort(key=lambda r: -sum(share.get(a, 0) for a in r.addresses))
        for i, r in enumerate(items, 1):
            r.priority = i
    return recs


# ───────────────────────────── 5. nawadnianie (FAO-56, rozdz. 8) ─────────────────────────────
def _stage_kc(cal: dict | None, kc_climate: dict | None) -> list[tuple[date, date, float, str]]:
    """Fazy z kalendarza → [(od, do, Kc, nazwa)]; Kc fazy pełni wzrostu skorygowane do klimatu (FAO-56 równ. 62)."""
    stages = (cal or {}).get("stages") or []
    out: list[tuple[date, date, float, str]] = []
    kcs = [s.get("kc") for s in stages if s.get("kc") is not None]
    if not kcs:
        return out
    top = max(kcs)
    for i, s in enumerate(stages):
        kc = s.get("kc")
        if kc is None:   # siew/wschody → Kc fazy początkowej; zbiór → Kc końcowe
            kc = next((x.get("kc") for x in stages[i + 1:] if x.get("kc") is not None), kcs[-1]) if i == 0 else kcs[-1]
        if kc == top and kc_climate and kc_climate.get("u2_ms") is not None and kc_climate.get("rh_min_pct") is not None:
            kc = fao56.kc_climate_adjust(kc, kc_climate["u2_ms"], kc_climate["rh_min_pct"])
        out.append((date.fromisoformat(str(s["start"])[:10]), date.fromisoformat(str(s["end"])[:10]), float(kc), s.get("name", "")))
    return out


def _kc_on(stages: list[tuple[date, date, float, str]], day: date) -> float | None:
    for a, b, kc, _ in stages:
        if a <= day <= b:
            return kc
    return None


def _mulch_saving(ctx: AnalysisContext, d: dict[str, dict | None]) -> dict | None:
    """Ile wody oszczędza mulcz w fazie początkowej (gleba odkryta; Kc ini ≈ parowanie z gleby, FAO-56 rozdz. 6–7)."""
    cal, w = d["crop_calendar"], d["weather_history"]
    st = [s for s in _stage_kc(cal, None)]
    clim = {m["month"]: m.get("et0_mean_mm") for m in (w or {}).get("monthly_climatology") or []}
    ini = next((s for s in st if "początk" in s[3].lower()), st[1] if len(st) > 1 else None) if st else None
    if not ini or not clim:
        return None
    a, b, kc, _ = ini
    days = (b - a).days + 1
    evap = 0.0
    dd = a
    while dd <= b:
        m = clim.get(dd.month)
        if m:
            evap += kc * m / 30.4
        dd += timedelta(days=1)
    saving = fao56.mulch_evaporation_saving(evap, 0.5)
    return {"days": days, "evap_mm": evap, "saving_mm": saving, "saving_m3": saving * ctx.parcel.area_ha * 10}


def irrigation(ctx: AnalysisContext, d: dict[str, dict | None]) -> IrrigationAdvice:
    cal, fc, w, soil = d["crop_calendar"], d["weather_forecast"], d["weather_history"], d["soil"]
    if not ctx.crop:
        return IrrigationAdvice(summary="Wybierz uprawę, aby ocenić potrzebę nawadniania.")
    crop = loader.get_item("crops", ctx.crop) or {}
    name = crop.get("name_pl", "Uprawa")
    if not cal or not cal.get("in_season_on_as_of"):
        return IrrigationAdvice(recommended="no", summary=f"{name} jest poza sezonem wegetacji "
                                f"({(cal or {}).get('current_stage') or 'brak danych'}) – nawadnianie nie ma teraz sensu.",
                                evidence=[_ev(f"faza: {(cal or {}).get('current_stage')}", "crop_calendar")] if cal else [])
    stages = _stage_kc(cal, (w or {}).get("kc_climate"))
    daily = (w or {}).get("daily") or {}
    if not stages or not daily.get("dates"):
        return IrrigationAdvice(summary="Brak danych pogodowych lub faz uprawy – nie liczymy bilansu wody w glebie.")
    awc = (soil or {}).get("awc_mm") or 150.0
    zr = min(1.5, crop.get("root_depth_m") or 1.0)
    p_tab = crop.get("p") or 0.5
    ky = crop.get("ky") or 1.0
    # start bilansu: początek faz w tym sezonie (gleba w pojemności polowej po zimie, Dr0 = 0), najwyżej 180 dni wstecz
    start = max(min(a for a, *_ in stages), ctx.as_of - timedelta(days=180))
    rows: list[tuple[date, float | None, float | None, float, bool]] = []
    for ds, p, e in zip(daily["dates"], daily["precip_mm"], daily["et0_mm"]):
        day = date.fromisoformat(str(ds)[:10])
        if start <= day <= ctx.as_of:
            kc = _kc_on(stages, day)
            if kc is not None:
                rows.append((day, p, e, kc, False))
    if not rows:
        return IrrigationAdvice(summary="Za mało danych od początku sezonu, by policzyć bilans wody w glebie.")
    horizon, label, src = 0, "", "weather_forecast"
    if fc and fc.get("dates"):
        for ds, p, e in zip(fc["dates"], fc.get("precip_mm") or [], fc.get("et0_mm") or []):
            day = date.fromisoformat(str(ds)[:10])
            if day > ctx.as_of and (kc := _kc_on(stages, day) or rows[-1][3]):
                rows.append((day, p, e, kc, True))
                horizon += 1
        label = f"prognoza {horizon} dni"
    else:   # analiza historyczna: scenariusz „bez deszczu” przy średnim ET0 z ostatnich 7 dni
        last7 = [r[2] for r in rows[-7:] if r[2] is not None]
        e_mean = sum(last7) / len(last7) if last7 else 3.0
        for k in range(1, 22):
            day = ctx.as_of + timedelta(days=k)
            rows.append((day, 0.0, e_mean, _kc_on(stages, day) or rows[-1][3], True))
        horizon, label, src = 21, "scenariusz bez deszczu (analiza historyczna)", "weather_history"
    bal = fao56.root_zone_balance(rows, awc, zr, p_tab)
    now = bal.last
    if now is None:
        return IrrigationAdvice(summary="Nie udało się policzyć bilansu wody w glebie.")
    ratio = bal.season_ratio()
    loss = fao56.yield_loss_fraction(ky, ratio, 1.0) if ratio is not None else None
    stress = bal.first_stress()
    days_to = (stress.day - ctx.as_of).days if stress else None
    series = [{"date": x.day.isoformat(), "dr_mm": x.dr, "raw_mm": x.raw, "taw_mm": x.taw, "forecast": x.forecast}
              for x in bal.days if x.day >= ctx.as_of - timedelta(days=60)]
    ev = [_ev(f"bilans wody w strefie korzeni od {start.strftime('%d.%m')}: ubyło {now.dr:.0f} mm z {now.taw:.0f} mm "
              f"wody dostępnej (łatwo dostępne {now.raw:.0f} mm)", "weather_history"),
          _ev(_pl_dec(f"zapas wody w glebie {awc:.0f} mm/m × korzenie {zr:.1f} m (FAO-56 równ. 82–83)"),
              "soil" if soil else "crop_calendar")]
    if ratio is not None and ratio < 0.999:
        ev.append(_ev(f"od początku sezonu rośliny zużyły {ratio:.0%} wody, której potrzebowały (Ks < 1 w {sum(1 for x in bal.days if not x.forecast and x.ks < 1)} dniach)", "weather_history"))
    if loss:
        ev.append(_ev(_pl_dec(f"szacowany spadek plonu przez niedobór wody: ok. {loss:.0%} (FAO-56 równ. 90, Ky = {ky:.2f})"), "crop_calendar"))
    common = dict(depletion_mm=now.dr, taw_mm=now.taw, raw_mm=now.raw, ks=now.ks, horizon_days=horizon,
                  season_et_ratio=ratio, yield_loss_pct=round(loss * 100, 1) if loss is not None else None,
                  soil_water=series, days_to_stress=days_to, stress_date=stress.day.isoformat() if stress else None)
    if now.dr > now.raw:
        dose = round(min(now.dr, 35.0))
        return IrrigationAdvice(recommended="yes", dose_mm=dose, deficit_mm=round(now.dr, 1),
                                timing="jak najszybciej, rano lub wieczorem (mniejsze straty na parowanie)"
                                       + (f"; uzupełnienie do pełna wymaga {now.dr:.0f} mm – podziel na 2 dawki" if now.dr > 35 else ""),
                                summary=f"Rośliny są już w stresie wodnym (Ks = {now.ks:.2f}). Gleba straciła {now.dr:.0f} mm wody, a bez "
                                        f"stresu roślina pobiera tylko {now.raw:.0f} mm. Dawka ok. {dose} mm (= {dose * 10} m³/ha). "
                                        "Pamiętaj o pozwoleniu wodnoprawnym.",
                                evidence=ev + [_ev(label, src)], **common)
    if stress and days_to is not None and days_to <= 7:
        dose = round(min(stress.dr, 35.0))
        return IrrigationAdvice(recommended="yes" if days_to <= 3 else "monitor", dose_mm=dose, deficit_mm=round(stress.dr, 1),
                                timing=f"przed {stress.day.strftime('%d.%m')}, rano lub wieczorem",
                                summary=f"Za ok. {days_to} dni ({stress.day.strftime('%d.%m')}) pole wejdzie w stres wodny"
                                        f"{' przy pogodzie z prognozy' if src == 'weather_forecast' else ', jeśli nie spadnie deszcz'}. "
                                        f"Przygotuj nawadnianie dawką ok. {dose} mm (= {dose * 10} m³/ha).",
                                evidence=ev + [_ev(label, src)], **common)
    return IrrigationAdvice(recommended="no",
                            summary=(f"Woda w glebie wystarcza – stres wodny dopiero za ok. {days_to} dni"
                                     f"{'' if src == 'weather_forecast' else ' bez deszczu'}." if days_to
                                     else f"Woda w glebie wystarcza na cały horyzont ({label}) – nawadnianie niepotrzebne."),
                            evidence=ev + [_ev(label, src)], **common)


# ───────────────────────────── blok ─────────────────────────────
def analyse_all(ctx: AnalysisContext, d: dict[str, dict | None], not_applicable: set[str] | None = None) -> AnalysisResult:
    missing = [DEP_TITLES[k] for k, v in d.items() if v is None and k not in (not_applicable or set())]
    a = assess(ctx, d)
    res = AnalysisResult(assessment=a, missing_blocks=missing)
    if a is None:
        res.limitations.append("Brak danych meteorologicznych i oceny suszy – nie da się ocenić sytuacji wodnej, "
                               "dlatego nie pokazujemy przyczyn ani rekomendacji.")
        return res
    res.causes = causes(ctx, d, a.field_check)
    res.water_balance = water_balance(ctx, d)
    res.recommendations = recommendations(ctx, d, res.causes, res.water_balance)
    res.irrigation = irrigation(ctx, d)
    if _strict_protected(d["protected_areas"]):
        res.limitations.append("Działka leży w parku narodowym lub rezerwacie – nie proponujemy budowy zbiorników, "
                               "zastawek ani urządzeń wodnych; każde działanie uzgodnij z dyrekcją parku / RDOŚ.")
    terr = d.get("terrain") or {}
    if terr.get("dem_source") and "zapasowe" in terr["dem_source"]:
        res.limitations.append(
            "Rzeźbę terenu policzyliśmy z modelu Copernicus 30 m, bo usługa GUGiK NMT chwilowo nie odpowiadała – zagłębienia "
            "i kierunki spływu są przybliżone" + (" i przy tej powierzchni działki ich nie oceniamy." if _coarse_terrain(ctx, terr)
                                                  else "; sprawdź je w terenie."))
    res.limitations += [
        "Progi oceny (punkty za KBW, susze, NDVI) i udziały przyczyn to szacunek zespołu – nie oficjalna klasyfikacja.",
        "Nie uwzględniamy drenażu (brak otwartej mapy drenaży w Polsce), nawadniania sąsiadów ani lokalnych burz "
        "poza siatką danych pogodowych.",
        "Zapas wody w glebie szacujemy z kategorii gleby i bilansu wodnego – bez pomiaru wilgotności na polu.",
        "Bilans FAO-56 bez spływu powierzchniowego i podsiąku z wód gruntowych, start z gleby w pojemności polowej "
        "na początku sezonu; Kc i Ky z tabel FAO-56 są ogólnoświatowe (dla Polski przybliżone).",
    ]
    if missing:
        res.limitations.append("Bez danych z bloków: " + ", ".join(missing) + " – te czynniki pominięto.")
    res.method = [
        "Ocena bieżąca: KBW z 60 dni względem normy z 10 lat, aktualna ocena suszy (SMSR / KBW działki / EDO), anomalia NDVI.",
        "Podatność wieloletnia: liczba sezonów z suszą rolniczą w 10 latach (progi KBW SMSR, rozp. MRiRW z 11.04.2019) "
        "skorygowana kategorią gleby SMSR.",
        "Przyczyny: średni KBW w sezonie (kwi–wrz), kategoria gleby i zapas wody, spadek terenu i linie spływu, rowy, wrażliwość uprawy.",
        "Rekomendacje: katalog naturalnych metod retencji (NWRM, KE 2014/2015), najpierw retencja, potem agrotechnika, "
        "nawadnianie na końcu.",
        "Nawadnianie: dobowy bilans wody w strefie korzeni FAO-56 (rozdz. 8, równ. 81–88) od początku faz uprawy, "
        "współczynnik stresu Ks (równ. 84), p skorygowane do ETc (tab. 22), Kc pełni wzrostu skorygowane do wiatru i "
        "wilgotności (równ. 62), spadek plonu 1 − Ya/Ym = Ky(1 − ETa/ETc) (równ. 90, Ky z tab. 24 za FAO-33).",
        "Bilans ilościowy: 1 mm na 1 ha = 10 m³; napływ do zagłębienia = nadwyżka KBW paź–mar × zlewnia D8 (górny szacunek).",
        "KBW × NDMI: pogoda (siatka ~10 km) zestawiona z wilgotnością liści z Sentinel-2 (20 m) na tej działce.",
    ]
    return res


class AnalysisConnector(Connector):
    key = "analysis"; title = "Ocena sytuacji wodnej i rekomendacje"; category = "derived"
    uses_crop = True
    live_ttl_s = 3 * 3600
    timeout_s = 20
    cache_version = 5   # 5: zgrubny DEM – bez zagłębień na małych działkach; 4: międzyplon/mulcz – gatunki i terminy (sowing), miesiące skrótami
    depends_on: ClassVar[tuple[str, ...]] = DEPS

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        from app.services.profile import run_block  # import lokalny: unikamy cyklu registry ↔ profile

        blocks = await asyncio.gather(*(run_block(k, ctx) for k in DEPS), return_exceptions=True)
        d = {k: _block_data(b) for k, b in zip(DEPS, blocks)}
        na = {k for k, b in zip(DEPS, blocks) if not isinstance(b, BaseException) and b.status == BlockStatus.not_applicable}
        res = analyse_all(ctx, d, na)
        snap = loader.meta("measures").get("snapshot_date")
        prov = [doc_prov("smsr_podstawy_2012", snap, notes="ocena suszy: KBW w okresach 60-dniowych i progi dla kategorii gleb; "
                         "wynik liczony z danych pobranych dla tej działki i daty"),
                _knowledge_prov("FAO-56 Crop evapotranspiration (Allen i in.) – dobowy bilans wody w strefie korzeni", snap,
                                url=FAO56_URL, notes="rozdz. 8 i 11: nawadnianie, mulcz"),
                doc_prov("nwrm_guide_2015", snap, notes="naturalne metody zatrzymywania wody (zastawki, oczka, pasy buforowe)"),
                doc_prov("cdr_eporadnik_2025", snap, notes="międzyplony, mulcz, mała retencja w gospodarstwie"),
                doc_prov("iung_sir66_6_retencja_gleby", snap, notes="praktyki zwiększające retencję wody w glebie")]
        if res.assessment is None:
            return self.block(BlockStatus.no_data, res, provenance=prov, uncertainty=res.limitations,
                              messages=["Brak danych do oceny sytuacji wodnej."])
        status = BlockStatus.ok if not res.missing_blocks else BlockStatus.partial
        return self.block(status, res, provenance=prov, uncertainty=res.limitations[:2])
