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
from datetime import date, timedelta
from typing import Any, ClassVar

from app.connectors.base import Connector
from app.contracts.models import (AnalysisContext, AnalysisResult, BlockStatus, Cause, DataBlock, Evidence,
                                  IrrigationAdvice, Recommendation, WaterAssessment)
from app.knowledge import loader
from app.knowledge.blocks import _block_data, _knowledge_prov

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
    s = f"{abs(v):.0f}".replace(".", ",")
    return (("+" if v > 0 else "−" if v < 0 else "") if signed else ("−" if v < 0 else "")) + s + " mm"


def _ev(text: str, block: str) -> Evidence:
    return Evidence(text=text, block=block)


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
        ev.append(_ev(f"NDVI {veg['anomaly']:+.2f} względem normy dla tej pory roku".replace(".", ",").replace("-", "−"), "vegetation"))
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
        ev.append(_ev(f"susza rolnicza w {n_years} z 10 ostatnich sezonów"
                      + (f" ({', '.join(map(str, years[-6:]))})" if years else ""), "drought"))
    if cat:
        ev.append(_ev(f"gleba kategorii {['I', 'II', 'III', 'IV'][cat - 1]} wg SMSR "
                      f"({['bardzo podatna', 'podatna', 'średnio podatna', 'mało podatna'][cat - 1]} na suszę)", "soil"))
    seasons = (w or {}).get("seasons") or []
    worst = min((s for s in seasons if s.get("cwb_apr_sep_mm") is not None), key=lambda s: s["cwb_apr_sep_mm"], default=None)
    if worst:
        ev.append(_ev(f"najsuchszy sezon IV–IX: {worst['year']}, KBW {_mm(worst['cwb_apr_sep_mm'], True)}", "weather_history"))

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
    hist_summary = (f"W ostatnich 10 latach susza rolnicza wystąpiła tu w {n_years} sezonach. " +
                    (f"Największe ryzyko niedoboru wody: {', '.join(MONTHS_PL[m - 1] for m in crit)}." if crit else ""))

    have = sum(x is not None for x in (w, dr, soil, veg))
    conf = "high" if have == 4 else "medium" if have >= 2 else "low"
    return WaterAssessment(current_level=cur_level, current_label_pl=CURRENT_LABEL[cur_level], current_summary=cur_summary,
                           historical_level=hist, historical_label_pl=HIST_LABEL[hist], historical_summary=hist_summary,
                           drought_years=years, critical_months=crit, confidence=conf, evidence=ev)


# ───────────────────────────── 2. przyczyny ─────────────────────────────
def causes(ctx: AnalysisContext, d: dict[str, dict | None]) -> list[Cause]:
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
        out.append((wt, Cause(key="gleba_niska_retencja", label_pl=CAUSE_LABEL["gleba_niska_retencja"],
                              explanation="Gleba lekka lub uboga w próchnicę szybko przesycha; więcej materii organicznej zwiększa zapas wody."
                              if wt >= 0.6 else "Gleba ma przeciętną zdolność zatrzymywania wody.", evidence=ev)))
    wt, ev = 0.0, []
    if terr:
        slope = terr.get("slope_mean_deg")
        if slope is not None:
            ev.append(_ev(f"średni spadek działki {slope:.1f}°".replace(".", ","), "terrain"))
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


# ───────────────────────────── 3–4. rekomendacje ─────────────────────────────
def recommendations(ctx: AnalysisContext, d: dict[str, dict | None], cs: list[Cause]) -> list[Recommendation]:
    terr, hyd, prot, soil, lc = d["terrain"], d["hydrology"], d["protected_areas"], d["soil"], d["land_cover"]
    measures = {m["id"]: m for m in loader.items("measures")}
    share = {c.key: c.share or 0 for c in cs}
    strict = _strict_protected(prot)
    crop = loader.get_item("crops", ctx.crop) if ctx.crop else None
    perennial = bool(crop and crop.get("type") == "wieloletnia")
    recs: list[Recommendation] = []

    def add(mid: str, title: str, why: str, ev: list[Evidence], when: str | None = None, where: dict | None = None):
        m = measures[mid]
        recs.append(Recommendation(measure_id=mid, group=m["group"], title=title, why=why, when=when or m.get("when"),
                                   addresses=list(m.get("addresses") or []), legal_ids=list(m.get("legal_ids") or []),
                                   funding_ids=list(m.get("funding") or []), where_geojson=where, evidence=ev))

    # retencja krajobrazowa – nie w parku narodowym / rezerwacie (budowa urządzeń praktycznie wykluczona)
    if not strict:
        ditches = sorted([x for x in (hyd or {}).get("nearest_water") or [] if x.get("kind") == "ditch"],
                         key=lambda x: x["distance_m"])
        if ditches and ditches[0]["distance_m"] <= 300:
            dch = ditches[0]
            add("zastawka_row", f"Zastawka na rowie {dch.get('name') or 'melioracyjnym'}",
                f"Rów {dch['distance_m']:.0f} m od działki odprowadza wodę poza gospodarstwo. Piętrzenie (zastawka) wiosną "
                "zatrzyma wodę z roztopów w okolicy i podniesie poziom wód gruntowych.",
                [_ev(f"rów melioracyjny: {dch['distance_m']:.0f} m od działki", "hydrology")], when="przed roztopami (II–III)")
        flood = (hyd or {}).get("in_flood_zone") or (hyd or {}).get("in_flood_hazard_area")
        deps = [f for f in ((terr or {}).get("depressions_geojson") or {}).get("features") or []
                if (f.get("properties") or {}).get("touches_parcel")]
        if deps and not flood:
            best = max(deps, key=lambda f: (f.get("properties") or {}).get("volume_m3") or 0)
            p = best.get("properties") or {}
            add("oczko_zbiornik", "Oczko wodne lub mały zbiornik w zagłębieniu terenu",
                f"Na działce jest naturalne zagłębienie (ok. {p.get('area_m2', 0):.0f} m², do {p.get('max_depth_m', 0):.1f} m), "
                "w którym zbiera się woda – mniej kopania. Do 5000 m² i 3 m głębokości wystarczy zgłoszenie wodnoprawne.".replace(".0 m", " m"),
                [_ev(f"zagłębienie bezodpływowe {p.get('area_m2', 0):.0f} m², głębokość do {p.get('max_depth_m', 0):.1f} m, "
                     f"pojemność ok. {p.get('volume_m3', 0):.0f} m³", "terrain"),
                 _ev("poza strefą zagrożenia powodziowego" if hyd and hyd.get("flood_zone_checked") else
                     "strefy powodziowej nie sprawdzono", "hydrology")],
                when="poza sezonem (X–III), po zgłoszeniu wodnoprawnym", where=best)
        slope = (terr or {}).get("slope_mean_deg")
        near_water = [x for x in (hyd or {}).get("nearest_water") or [] if x["distance_m"] <= 100 and x.get("kind") != "ditch"]
        if share.get("odplyw_powierzchniowy", 0) >= 0.25 or (slope is not None and slope > 2) or near_water:
            ev = []
            if slope is not None:
                ev.append(_ev(f"średni spadek {slope:.1f}°".replace(".", ","), "terrain"))
            if near_water:
                ev.append(_ev(f"{near_water[0].get('name') or 'ciek'} {near_water[0]['distance_m']:.0f} m od działki", "hydrology"))
            add("pas_buforowy", "Pas zieleni lub zadrzewienie na granicy pola",
                "Pas traw, krzewów lub drzew w poprzek spływu spowalnia odpływ, zatrzymuje glebę i ogranicza wysuszanie przez wiatr.",
                ev, when="jesień lub wczesna wiosna")
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
            [_ev(f"węgiel organiczny {soc:.0f} g/kg", "soil")] if soc is not None else [], when="VII–VIII, zaraz po zbiorze")
    if g >= 0.2 or not perennial:
        add("resztki_mulcz", "Zostaw resztki pożniwne jako mulcz",
            "Mulcz na powierzchni zmniejsza parowanie z wierzchniej warstwy gleby w okresie najczęstszych susz.",
            [_ev(f"udział przyczyny „gleba słabo zatrzymuje wodę”: {g:.0%}", "soil")] if g else [], when="po zbiorze")
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
            [_ev(f"średni spadek {slope:.1f}°".replace(".", ","), "terrain")])

    # priorytet = suma udziałów przyczyn, na które działa rekomendacja (w obrębie grupy)
    for grp in ("retencja_krajobrazowa", "agrotechnika"):
        items = [r for r in recs if r.group == grp]
        items.sort(key=lambda r: -sum(share.get(a, 0) for a in r.addresses))
        for i, r in enumerate(items, 1):
            r.priority = i
    return recs


# ───────────────────────────── 5. nawadnianie ─────────────────────────────
def irrigation(ctx: AnalysisContext, d: dict[str, dict | None]) -> IrrigationAdvice:
    cal, fc, w, soil = d["crop_calendar"], d["weather_forecast"], d["weather_history"], d["soil"]
    if not ctx.crop:
        return IrrigationAdvice(summary="Wybierz uprawę, aby ocenić potrzebę nawadniania.")
    crop = loader.get_item("crops", ctx.crop) or {}
    if not cal or not cal.get("in_season_on_as_of"):
        return IrrigationAdvice(recommended="no", summary=f"{crop.get('name_pl', 'Uprawa')} jest poza sezonem wegetacji "
                                f"({(cal or {}).get('current_stage') or 'brak danych'}) – nawadnianie nie ma teraz sensu.",
                                evidence=[_ev(f"faza: {(cal or {}).get('current_stage')}", "crop_calendar")] if cal else [])
    stage = next((s for s in cal.get("stages") or [] if str(s["start"]) <= ctx.as_of.isoformat() <= str(s["end"])), None)
    kc = (stage or {}).get("kc") or 0.5
    ev: list[Evidence] = []
    if fc and fc.get("dates"):
        et0 = [v or 0 for v in fc.get("et0_mm") or []]
        pr = [v or 0 for v in fc.get("precip_mm") or []]
        horizon, src = len(fc["dates"]), "weather_forecast"
        label = f"prognoza {horizon} dni"
    elif w and w.get("daily", {}).get("dates"):
        dl = w["daily"]
        idx = [i for i, x in enumerate(dl["dates"]) if ctx.as_of - timedelta(days=10) < date.fromisoformat(str(x)[:10]) <= ctx.as_of]
        et0 = [dl["et0_mm"][i] or 0 for i in idx]
        pr = [dl["precip_mm"][i] or 0 for i in idx]
        horizon, src = len(idx), "weather_history"
        label = f"ostatnie {horizon} dni (analiza historyczna – bez prognozy)"
    else:
        return IrrigationAdvice(summary="Brak danych pogodowych – nie oceniamy potrzeby nawadniania.")
    etc = sum(e * kc for e in et0)
    peff = 0.8 * sum(pr)
    deficit = etc - peff
    ev.append(_ev(f"{label}: zużycie wody przez uprawę {etc:.0f} mm (ET₀ × Kc {kc:.2f}), opad efektywny {peff:.0f} mm"
                  .replace(".", ","), src))
    awc = (soil or {}).get("awc_mm") or 150.0
    taw = awc * min(1.5, crop.get("root_depth_m") or 1.0)
    raw = taw * (crop.get("p") or 0.5)
    depletion = max(0.0, -((w or {}).get("cwb_60d_mm") or 0.0))
    depletion = min(depletion, taw)
    ev.append(_ev(f"zapas wody łatwo dostępnej dla korzeni ok. {raw:.0f} mm; ubytek z 60 dni ok. {depletion:.0f} mm (szacunek)",
                  "soil" if soil else "weather_history"))
    need = depletion + max(0.0, deficit)
    if need >= raw:
        dose = max(10.0, min(30.0, need - 0.5 * raw))
        return IrrigationAdvice(recommended="yes", deficit_mm=round(deficit, 1), dose_mm=round(dose), horizon_days=horizon,
                                timing="w ciągu kilku dni, rano lub wieczorem (mniejsze straty na parowanie)",
                                summary=f"Zapas wody w glebie jest na wyczerpaniu ({stage['name'] if stage else 'sezon'}) – "
                                        f"nawadnianie dawką ok. {dose:.0f} mm uzasadnione. Pamiętaj o pozwoleniu wodnoprawnym.",
                                evidence=ev)
    if need >= 0.6 * raw:
        return IrrigationAdvice(recommended="monitor", deficit_mm=round(deficit, 1), horizon_days=horizon,
                                summary="Zapas wody maleje – obserwuj uprawę i prognozę; nawadnianie może być potrzebne w najbliższych dniach.",
                                evidence=ev)
    return IrrigationAdvice(recommended="no", deficit_mm=round(deficit, 1), horizon_days=horizon,
                            summary="Woda w glebie wystarcza na najbliższe dni – nawadnianie teraz niepotrzebne.", evidence=ev)


# ───────────────────────────── blok ─────────────────────────────
def analyse_all(ctx: AnalysisContext, d: dict[str, dict | None], not_applicable: set[str] | None = None) -> AnalysisResult:
    missing = [DEP_TITLES[k] for k, v in d.items() if v is None and k not in (not_applicable or set())]
    a = assess(ctx, d)
    res = AnalysisResult(assessment=a, missing_blocks=missing)
    if a is None:
        res.limitations.append("Brak danych meteorologicznych i oceny suszy – nie da się ocenić sytuacji wodnej, "
                               "dlatego nie pokazujemy przyczyn ani rekomendacji.")
        return res
    res.causes = causes(ctx, d)
    res.recommendations = recommendations(ctx, d, res.causes)
    res.irrigation = irrigation(ctx, d)
    if _strict_protected(d["protected_areas"]):
        res.limitations.append("Działka leży w parku narodowym lub rezerwacie – nie proponujemy budowy zbiorników, "
                               "zastawek ani urządzeń wodnych; każde działanie uzgodnij z dyrekcją parku / RDOŚ.")
    res.limitations += [
        "Progi oceny (punkty za KBW, susze, NDVI) i udziały przyczyn to szacunek zespołu – nie oficjalna klasyfikacja.",
        "Nie uwzględniamy drenażu (brak otwartej mapy drenaży w Polsce), nawadniania sąsiadów ani lokalnych burz "
        "poza siatką danych pogodowych.",
        "Zapas wody w glebie szacujemy z kategorii gleby i bilansu wodnego – bez pomiaru wilgotności na polu.",
    ]
    if missing:
        res.limitations.append("Bez danych z bloków: " + ", ".join(missing) + " – te czynniki pominięto.")
    res.method = [
        "Ocena bieżąca: KBW z 60 dni względem normy z 10 lat, aktualna ocena suszy (SMSR / KBW działki / EDO), anomalia NDVI.",
        "Podatność wieloletnia: liczba sezonów z suszą rolniczą w 10 latach (progi KBW SMSR, rozp. MRiRW z 11.04.2019) "
        "skorygowana kategorią gleby SMSR.",
        "Przyczyny: średni KBW IV–IX, kategoria gleby i zapas wody, spadek terenu i linie spływu, rowy, wrażliwość uprawy.",
        "Rekomendacje: katalog naturalnych metod retencji (NWRM, KE 2014/2015), najpierw retencja, potem agrotechnika, "
        "nawadnianie na końcu; nawadnianie wg bilansu FAO-56 (ET₀ × Kc − 0,8 × opad).",
    ]
    return res


class AnalysisConnector(Connector):
    key = "analysis"; title = "Ocena sytuacji wodnej i rekomendacje"; category = "derived"
    uses_crop = True
    live_ttl_s = 3 * 3600
    timeout_s = 20
    cache_version = 2
    depends_on: ClassVar[tuple[str, ...]] = DEPS

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        from app.services.profile import run_block  # import lokalny: unikamy cyklu registry ↔ profile

        blocks = await asyncio.gather(*(run_block(k, ctx) for k in DEPS), return_exceptions=True)
        d = {k: _block_data(b) for k, b in zip(DEPS, blocks)}
        na = {k for k, b in zip(DEPS, blocks) if not isinstance(b, BaseException) and b.status == BlockStatus.not_applicable}
        res = analyse_all(ctx, d, na)
        prov = [_knowledge_prov("reguły analizy (knowledge/analysis.py) + katalog działań (retention_measures.yaml)",
                                loader.meta("measures").get("snapshot_date"),
                                notes="wynik liczony z bloków danych pobranych dla tej działki i daty")]
        if res.assessment is None:
            return self.block(BlockStatus.no_data, res, provenance=prov, uncertainty=res.limitations,
                              messages=["Brak danych do oceny sytuacji wodnej."])
        status = BlockStatus.ok if not res.missing_blocks else BlockStatus.partial
        return self.block(status, res, provenance=prov, uncertainty=res.limitations[:2])
