"""Bloki profilu liczone z lokalnej bazy wiedzy + faktów o działce (zespół PRODUCT).

- CropCalendarConnector → CropCalendarInfo: na podstawie crops.yaml i ctx.as_of – czy uprawa jest w sezonie,
  fazy FAO-56 z datami i Kc, aktualna faza, okresy krytyczne, czy to dobry termin siewu, ostrzeżenia,
  uprawy możliwe do siewu w tym terminie.
- LegalContextConnector → LegalContextInfo: reguły (nie LLM) z legal_pl + procedures + funding,
  parametryzowane faktami z bloków Agenta A (hydrology, protected_areas, terrain). Liczony w 2. fali
  orkiestratora (depends_on). Gdy blok A nie ma danych, reguła działa bez faktu i mówi wprost, czego nie sprawdzono.
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta
from typing import Any, ClassVar

from app.connectors.base import Connector
from app.contracts.models import (AnalysisContext, BlockStatus, CropCalendarInfo, CropStage, DataBlock,
                                  LegalContextInfo, LegalHint, Provenance)
from app.knowledge import loader

MONTHS_PL = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień",
             "październik", "listopad", "grudzień"]
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
         "XI": 11, "XII": 12}
FAO_STAGE_NAMES = ["faza początkowa", "rozwój roślin", "pełnia wzrostu", "dojrzewanie"]
WINDOW_RE = re.compile(r"^(\d{2})-(\d{2})\.\.(\d{2})-(\d{2})$")
ROMAN_RANGE_RE = re.compile(r"\(([IVX]+)(?:\s*[–-]\s*([IVX]+))?\)")


# ───────────────────────────── pomocnicze ─────────────────────────────
def _knowledge_prov(collection_label: str, snapshot: Any, notes: str | None = None) -> Provenance:
    from app.connectors.base import now_utc
    snap = snapshot if isinstance(snapshot, date) else None
    if isinstance(snapshot, str):
        try:
            snap = date.fromisoformat(snapshot)
        except ValueError:
            snap = None
    return Provenance(source_name=f"Lokalna baza wiedzy: {collection_label}", retrieved_at=now_utc(),
                      mode="local_snapshot", snapshot_date=snap,
                      source_url="https://github.com/Jejis06/task_KOWR_hacknation/tree/main/data/knowledge",
                      licence="treści własne zespołu na podstawie źródeł publicznych (lista w `sources`)", notes=notes)


def _md(year: int, mmdd: str) -> date:
    m, d = (int(x) for x in mmdd.split("-"))
    if m == 2 and d == 29:
        d = 28
    return date(year, m, d)


def parse_window(text: Any, year: int) -> tuple[date, date] | None:
    """„09-15..10-20” → (15.09.year, 20.10.year); inne formaty (opis słowny, None) → None."""
    if not isinstance(text, str):
        return None
    m = WINDOW_RE.match(text.strip())
    if not m:
        return None
    a = _md(year, f"{m.group(1)}-{m.group(2)}")
    b = _md(year, f"{m.group(3)}-{m.group(4)}")
    return a, b


def roman_months(text: str) -> set[int]:
    """„kwitnienie (V–VI)” → {5, 6}."""
    out: set[int] = set()
    for a, b in ROMAN_RANGE_RE.findall(text):
        if a not in ROMAN:
            continue
        start = ROMAN[a]
        end = ROMAN.get(b, start) if b else start
        m = start
        while True:
            out.add(m)
            if m == end:
                break
            m = m % 12 + 1
    return out


def fmt(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def fmt_dm(d: date) -> str:
    return d.strftime("%d.%m")


def _stages(item: dict[str, Any], year: int) -> list[CropStage]:
    start = _md(year, item["stages_start"])
    kc = item.get("kc") or [None, None, None]
    kc_ini, kc_mid, kc_end = (kc + [None, None, None])[:3]
    kc_dev = round((kc_ini + kc_mid) / 2, 2) if kc_ini is not None and kc_mid is not None else None
    kcs = [kc_ini, kc_dev, kc_mid, kc_end]
    out: list[CropStage] = []
    cur = start
    for name, days, k in zip(FAO_STAGE_NAMES, item.get("stages") or [], kcs):
        end = cur + timedelta(days=int(days) - 1)
        out.append(CropStage(name=name, start=cur, end=end, kc=k))
        cur = end + timedelta(days=1)
    return out


def _season(item: dict[str, Any], as_of: date) -> tuple[list[CropStage], date, date]:
    """Zwraca (fazy łącznie z jesienią/zimą i zbiorem, początek sezonu, koniec sezonu) dla kampanii
    właściwej dla daty analizy."""
    kind = item.get("type")
    y = as_of.year
    if kind == "ozima":
        h_end = parse_window(item.get("harvest"), y)
        harvest_end = h_end[1] if h_end else _stages(item, y)[-1].end
        hy = y if as_of <= harvest_end else y + 1     # rok zbioru tej kampanii
        sow = parse_window(item.get("sowing"), hy - 1)
        fao = _stages(item, hy)
        sow_start = sow[0] if sow else date(hy - 1, 9, 1)
        autumn_end = date(hy - 1, 11, 30)
        stages = [CropStage(name="siew, wschody i jesienny rozwój", start=sow_start, end=autumn_end,
                            kc=fao[0].kc if fao else None),
                  CropStage(name="spoczynek zimowy", start=autumn_end + timedelta(days=1),
                            end=fao[0].start - timedelta(days=1) if fao else date(hy, 3, 1), kc=None)]
        stages += fao
        h = parse_window(item.get("harvest"), hy)
        if h:
            stages.append(CropStage(name="zbiór", start=h[0], end=h[1], kc=None))
        return stages, sow_start, stages[-1].end

    # jare i wieloletnie: kampania w roku kalendarzowym; po jej końcu pokazujemy następny rok
    def build(year: int) -> tuple[list[CropStage], date, date]:
        fao = _stages(item, year)
        stages = list(fao)
        sow = parse_window(item.get("sowing"), year)
        if sow and kind == "jara" and sow[0] < fao[0].start:
            stages.insert(0, CropStage(name="siew i wschody", start=sow[0],
                                       end=fao[0].start - timedelta(days=1), kc=None))
        h = parse_window(item.get("harvest"), year)
        if h:
            stages.append(CropStage(name="zbiór", start=max(h[0], fao[-1].start), end=h[1], kc=None))
        start = stages[0].start
        end = max(s.end for s in stages)
        return stages, start, end

    stages, start, end = build(y)
    if as_of > end:
        stages, start, end = build(y + 1)
    return stages, start, end


def _sowing_suggestions(as_of: date, exclude: str | None = None) -> list[str]:
    out: list[str] = []
    for it in loader.items("crops"):
        if it["id"] == exclude:
            continue
        w = parse_window(it.get("sowing"), as_of.year)
        if not w:
            continue
        if w[0] <= as_of <= w[1]:
            out.append(f"{it['name_pl']} (siew do {fmt_dm(w[1])})")
        elif timedelta(0) < (w[0] - as_of) <= timedelta(days=21):
            out.append(f"{it['name_pl']} (siew od {fmt_dm(w[0])})")
    return out


def _winter_rules(as_of: date) -> list[str]:
    rules = loader.load("crops").get("winter_rules", [])
    m = as_of.month
    out = []
    for r in rules:
        if r.startswith("Siew jesienny") and m in (9, 10):
            out.append(r)
        elif r.startswith("XI–II") and m in (11, 12, 1, 2):
            out.append(r)
    return out


def crop_calendar(as_of: date, crop: str | None) -> tuple[BlockStatus, CropCalendarInfo | None, list[str], list[str]]:
    """Czysta funkcja (łatwa do testów): status, dane, uncertainty, messages."""
    meta = loader.meta("crops")
    uncertainty = ["Terminy siewu i zbioru są typowe dla Polski – lokalnie różnią się o ±2 tygodnie "
                   "(region, przebieg pogody, odmiana).",
                   "Długości faz i współczynniki Kc według FAO-56 dla klimatu umiarkowanego – wartości szacunkowe."]
    if not crop:
        in_season = date(as_of.year, 4, 1) <= as_of <= date(as_of.year, 10, 31)
        warnings = ["Nie wybrano uprawy – pokazuję tylko ogólny stan okresu wegetacji. "
                    "Wybierz uprawę, aby zobaczyć fazy rozwoju i okresy krytyczne."]
        warnings += _winter_rules(as_of)
        info = CropCalendarInfo(
            crop="", crop_name_pl="nie wybrano uprawy", in_season_on_as_of=in_season,
            current_stage="okres wegetacji" if in_season else "poza okresem wegetacji",
            warnings=warnings, suggested_crops_now=_sowing_suggestions(as_of),
        )
        uncertainty.append(f"Okres wegetacji przyjęto orientacyjnie (IV–X). {meta.get('growing_season_pl', '')}")
        return BlockStatus.ok, info, uncertainty, []

    item = loader.get_item("crops", crop)
    if item is None:
        return BlockStatus.no_data, None, [], [f"Nieznana uprawa „{crop}” – brak w bazie wiedzy (crops.yaml)."]

    stages, start, end = _season(item, as_of)
    in_season = start <= as_of <= end
    current = next((s.name for s in stages if s.start <= as_of <= s.end), None)
    if current is None:
        current = "przed siewem" if as_of < start else "po zbiorze"
    if item.get("type") == "wieloletnia" and not in_season:
        current = "spoczynek (poza sezonem)"

    warnings: list[str] = []
    name = item["name_pl"]
    sow_now = parse_window(item.get("sowing"), as_of.year)
    sowing_ok: bool | None = None
    if sow_now:
        sowing_ok = sow_now[0] <= as_of <= sow_now[1]
        details = []
        if item.get("min_soil_temp_sowing_c"):
            details.append(f"przy glebie ≥{item['min_soil_temp_sowing_c']} °C")
        if item.get("vegetation_days"):
            vd = item["vegetation_days"]
            details.append(f"wegetacja {vd[0]}–{vd[1]} dni")
        det = f" ({', '.join(details)})" if details else ""
        window_txt = f"{fmt_dm(sow_now[0])}–{fmt_dm(sow_now[1])}"
        if sowing_ok:
            warnings.append(f"Teraz jest termin siewu ({name}: {window_txt}{det}).")
        elif as_of < sow_now[0] and not in_season:
            days = (sow_now[0] - as_of).days
            warnings.append(f"{MONTHS_PL[as_of.month - 1].capitalize()}: na siew jest za wcześnie "
                            f"({name}: termin {window_txt}{det}, za {days} dni).")
        elif as_of > sow_now[1] and not in_season:
            nxt = parse_window(item.get("sowing"), as_of.year + 1)
            warnings.append(f"{MONTHS_PL[as_of.month - 1].capitalize()}: siew w tym roku już niemożliwy "
                            f"({name}: termin {window_txt}{det}); najbliższy termin od "
                            f"{fmt(nxt[0]) if nxt else 'przyszłego roku'}.")
    elif item.get("sowing"):
        warnings.append(f"Termin siewu/sadzenia: {item['sowing']}.")

    critical = list(item.get("critical") or [])
    active = [c for c in critical if as_of.month in roman_months(c)]
    if in_season and active:
        warnings.append("Teraz trwa okres krytyczny dla wody: " + "; ".join(active) +
                        ". Niedobór wody w tym czasie najbardziej obniża plon.")
    if not in_season:
        warnings += _winter_rules(as_of)
    if item.get("type") == "ozima" and in_season and current == "spoczynek zimowy":
        warnings.append("Uprawa w spoczynku zimowym – zapotrzebowanie na wodę minimalne; "
                        "ważny jest zapas wody w glebie przed ruszeniem wegetacji wiosną.")

    info = CropCalendarInfo(
        crop=crop, crop_name_pl=name, in_season_on_as_of=in_season, current_stage=current,
        stages=stages, critical_water_periods=critical, sowing_ok_now=sowing_ok,
        warnings=warnings, suggested_crops_now=_sowing_suggestions(as_of, exclude=crop),
    )
    return BlockStatus.ok, info, uncertainty, []


# ───────────────────────────── bloki ─────────────────────────────
class CropCalendarConnector(Connector):
    key = "crop_calendar"; title = "Kalendarz uprawy i okres wegetacji"; category = "knowledge"
    uses_crop = True
    live_ttl_s = 24 * 3600
    cache_version = 2

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        status, info, unc, msgs = crop_calendar(ctx.as_of, ctx.crop)
        meta = loader.meta("crops")
        prov = _knowledge_prov("kalendarz upraw (crops.yaml)", meta.get("snapshot_date"),
                               notes="; ".join(meta.get("sources", [])))
        return self.block(status, data=info, provenance=[prov], uncertainty=unc, messages=msgs)


def _block_data(blk: DataBlock[Any] | BaseException) -> dict[str, Any] | None:
    if isinstance(blk, BaseException) or blk.status not in (BlockStatus.ok, BlockStatus.partial):
        return None
    d = blk.data
    if d is None:
        return None
    return d.model_dump(mode="json") if hasattr(d, "model_dump") else dict(d)


STATUS_PL = {"ok": "sprawdzono", "partial": "sprawdzono częściowo", "no_data": "brak danych",
             "not_applicable": "nie dotyczy", "error": "błąd źródła", "not_implemented": "jeszcze niedostępne"}

DEP_LABEL = {"hydrology": "wody i strefy powodziowe", "protected_areas": "obszary chronione",
             "terrain": "ukształtowanie terenu"}


def fee_for(procedure_id: str, year: int) -> tuple[float | None, int | None]:
    proc = loader.get_item("procedures", procedure_id) or {}
    fees = proc.get("fees") or {}
    if str(year) in fees:
        return float(fees[str(year)]), year
    years = sorted(int(k) for k in fees if str(k).isdigit())
    if not years:
        return (float(proc["fee_pln"]), None) if proc.get("fee_pln") else (None, None)
    y = max([k for k in years if k <= year], default=years[0])
    return float(fees[str(y)]), y


def legal_hints(ctx: AnalysisContext, hydro: dict | None, prot: dict | None,
                terr: dict | None) -> list[LegalHint]:
    """Reguły. Każdy fakt pochodzi z bloku danych; brak bloku = wpis w `unchecked`, nigdy założenie."""
    rules = {r["id"]: r for r in loader.items("legal_pl")}

    def src(*ids: str) -> list[str]:
        out: list[str] = []
        for i in ids:
            out += rules.get(i, {}).get("sources", [])
        return list(dict.fromkeys(out))

    year = ctx.as_of.year
    area_ha = ctx.parcel.area_ha

    # ── fakty ──
    flood = hydro.get("in_flood_zone") if hydro else None
    flood_checked = bool(hydro and hydro.get("flood_zone_checked"))
    waters = (hydro or {}).get("nearest_water") or []
    ditches = sorted([w for w in waters if w.get("kind") == "ditch"], key=lambda w: w.get("distance_m", 1e9))
    rivers = sorted([w for w in waters if w.get("kind") in ("river", "stream")], key=lambda w: w.get("distance_m", 1e9))
    gw_depth = (hydro or {}).get("groundwater_depth_m")
    gzwp = (hydro or {}).get("gzwp")
    board = (hydro or {}).get("water_management_board")
    hits = (prot or {}).get("hits") or []
    natura = [h for h in hits if "natura" in (h.get("kind") or "").lower()]
    strict = [h for h in hits if any(k in (h.get("kind") or "").lower() for k in ("rezerwat", "park narodowy"))]
    position = (terr or {}).get("position")
    pos_label = (terr or {}).get("position_label_pl")
    depressions = (terr or {}).get("depressions_geojson") or {}
    n_depr = len(depressions.get("features") or []) if isinstance(depressions, dict) else 0
    slope = (terr or {}).get("slope_mean_deg")

    unchecked_hydro = [] if hydro else ["strefa zagrożenia powodziowego i odległość do wód (blok „Wody” bez danych)"]
    unchecked_prot = [] if prot else ["obszary chronione – Natura 2000, rezerwaty (blok bez danych)"]
    unchecked_terr = [] if terr else ["ukształtowanie terenu i zagłębienia (blok bez danych)"]
    where = f" Właściwy organ: {board}." if board else " Właściwy organ: Nadzór Wodny Wód Polskich dla Twojej gminy."

    def prot_caution() -> str | None:
        parts = []
        if strict:
            parts.append("działka w rezerwacie/parku narodowym (" + ", ".join(h.get("name") or h["kind"] for h in strict) +
                         ") – roboty ziemne zwykle wykluczone")
        if natura:
            parts.append("Natura 2000 (" + ", ".join(h.get("name") or h.get("code") or h["kind"] for h in natura) +
                         ") – możliwe uzgodnienia z RDOŚ i ocena oddziaływania")
        return "; ".join(parts) or None

    hints: list[LegalHint] = []

    # 1. staw / zbiornik
    fee, fy = fee_for("zgloszenie_wodnoprawne", year)
    why = ("Staw do 5000 m² i do 3 m głębokości, napełniany tylko wodą z opadów, roztopów lub gruntową, "
           "oddziałujący tylko na Twój grunt – wystarczy zgłoszenie wodnoprawne (organ ma 30 dni na sprzeciw). "
           "Większy albo zasilany z rzeki/rowu – pozwolenie wodnoprawne. Kilka stawów na jednym gruncie się sumuje.")
    facts, caution, group = [], None, "notification"
    if flood:
        caution = (f"Działka leży w strefie zagrożenia powodziowego (scenariusz {flood}) – budowa zbiornika jest tam "
                   "poważnie ograniczona (ryzyko zniszczenia, odrębna procedura). Zacznij od konsultacji z Wodami Polskimi.")
        group = "depends"
        facts.append(f"strefa powodziowa: {flood}")
    elif flood_checked:
        facts.append("poza mapowanymi strefami zagrożenia powodziowego (ISOK)")
    if n_depr or position in ("depression", "valley"):
        facts.append(f"teren: {pos_label or position}" + (f", {n_depr} zagłębień bezodpływowych" if n_depr else "") +
                     " – naturalne miejsce gromadzenia wody, mniej kopania")
    pc = prot_caution()
    if pc:
        caution = f"{caution} {pc}." if caution else pc[0].upper() + pc[1:] + "."
        if strict:
            group = "depends"
    hints.append(LegalHint(
        topic="staw", title="Staw lub zbiornik retencyjny (do 5000 m², do 3 m)", requirement="zgłoszenie wodnoprawne",
        group=group, why=why + where, procedure_id="zgloszenie_wodnoprawne",
        legal_ids=["staw_zgloszenie", "staw_pozwolenie", "ograniczenia_lokalizacji"], status="OK",
        sources=src("staw_zgloszenie", "staw_pozwolenie"), fee_pln=fee, fee_year=fy, facts_used=facts,
        unchecked=unchecked_hydro + unchecked_prot + unchecked_terr, caution=caution))

    # 2. oczko do 50 m²
    hints.append(LegalHint(
        topic="oczko", title="Małe szczelne oczko wodne do 50 m²", requirement="brak formalności wodnoprawnych",
        group="none", legal_ids=["oczko_male"], status="OK", sources=src("oczko_male"),
        why=("Szczelne (z izolacją) oczko do 50 m², które nie zmienia stosunków wodnych – bez formalności. "
             "Uwaga: zbiornik bez szczelnej izolacji albo połączony z rowem/ciekiem jest urządzeniem wodnym "
             "niezależnie od wielkości. Grobla, mnich czy przepust – sprawdź w starostwie.")))

    # 3. zastawka / zatrzymanie wody w istniejącym rowie
    facts, unchecked = [], list(unchecked_hydro)
    if ditches:
        d = ditches[0]
        facts.append(f"najbliższy rów: {d.get('name') or 'bez nazwy'}, ok. {round(d['distance_m'])} m od działki")
        near = d["distance_m"] <= 200
        why = (("Rów jest w zasięgu 200 m – " if near else "Najbliższy rów jest dalej niż 200 m. ") +
               "zatrzymywanie wody w istniejącym rowie (np. zastawką) nie wymaga zgłoszenia ani pozwolenia. "
               "Jeśli rów biegnie przez kilka działek – potrzebna zgoda sąsiadów (porozumienie albo spółka wodna). "
               "Przebudowa rowu albo nowe urządzenie melioracyjne – zgłoszenie lub pozwolenie wodnoprawne.")
    else:
        if hydro:
            facts.append("w danych nie znaleziono rowów melioracyjnych w pobliżu działki")
        why = ("Zatrzymywanie wody w istniejącym rowie (np. zastawką) nie wymaga zgłoszenia ani pozwolenia. "
               "Przy rowie przez kilka działek – zgoda sąsiadów. Przebudowa rowu – pozwolenie wodnoprawne.")
        if not hydro:
            why += " Nie sprawdziliśmy, czy w pobliżu działki jest rów."
    hints.append(LegalHint(
        topic="rów", title="Zastawka – zatrzymanie wody w istniejącym rowie", requirement="brak (zatrzymanie wody)",
        group="none", why=why, legal_ids=["row_zatrzymanie", "row_przebudowa", "melioracje_utrzymanie"],
        status="OK", sources=src("row_zatrzymanie", "row_przebudowa"), facts_used=facts, unchecked=unchecked))

    # 4. studnia ≤30 m
    limit_mm = 5 * 365 / (area_ha * 10) if area_ha > 0 else None  # 1 mm na 1 ha = 10 m³
    facts = []
    if gw_depth:
        facts.append(f"głębokość do pierwszego poziomu wodonośnego (MHP): {gw_depth}")
    if limit_mm is not None:
        facts.append(f"limit 5 m³/dobę (średnio w roku) = 1825 m³/rok ≈ {limit_mm:.0f} mm wody na całą działkę "
                     f"({area_ha:.2f} ha) rocznie")
    hints.append(LegalHint(
        topic="studnia", title="Studnia do 30 m na własne potrzeby", requirement="brak (zwykłe korzystanie z wód)",
        group="none", legal_ids=["zwykle_korzystanie", "studnia_do_30m", "abolicja_studnie"], status="OK",
        sources=src("studnia_do_30m", "zwykle_korzystanie"), facts_used=facts,
        unchecked=[] if hydro else ["głębokość wód podziemnych (blok „Wody” bez danych)"],
        why=("Studnia do 30 m na potrzeby własne gospodarstwa, przy poborze średnio do 5 m³ na dobę w skali roku – "
             "bez pozwolenia i bez zgłoszenia. Nawadnianie upraw deszczownią ze studni wykracza poza zwykłe korzystanie. "
             "Masz studnię bez wymaganej zgody? Wniosek o legalizację złożony do 31.12.2027 zwalnia z opłaty "
             "legalizacyjnej (ok. 6,6 tys. zł) i kar.")))

    # 5. studnia głębinowa
    fee, fy = fee_for("pozwolenie_wodnoprawne", year)
    facts = [f"Główny Zbiornik Wód Podziemnych: {gzwp}"] if gzwp else []
    hints.append(LegalHint(
        topic="studnia", title="Studnia głębinowa (>30 m) albo pobór ponad 5 m³/dobę", requirement="pozwolenie wodnoprawne",
        group="permit", procedure_id="studnia_glebinowa", legal_ids=["studnia_glebinowa"], status="OK",
        sources=src("studnia_glebinowa"), fee_pln=fee, fee_year=fy, facts_used=facts,
        why=("Potrzebne: projekt robót geologicznych zatwierdzony przez starostę, dokumentacja hydrogeologiczna "
             "i pozwolenie wodnoprawne na pobór. Za pobór wód podziemnych płaci się 0,068 zł/m³ "
             "(nawadnianie – bez opłaty stałej).") + where))

    # 6. nawadnianie z rzeki / cieku
    facts = []
    if rivers:
        r = rivers[0]
        facts.append(f"najbliższy ciek: {r.get('name') or 'bez nazwy'}, ok. {round(r['distance_m'])} m")
    hints.append(LegalHint(
        topic="nawadnianie", title="Nawadnianie wodą z rzeki lub cieku (pompa)", requirement="pozwolenie wodnoprawne",
        group="permit", procedure_id="pozwolenie_wodnoprawne", legal_ids=["pobor_z_cieku", "nawadnianie_pozwolenie"],
        status="OK", sources=src("pobor_z_cieku", "nawadnianie_pozwolenie"), fee_pln=fee, fee_year=fy,
        facts_used=facts, unchecked=list(unchecked_hydro),
        why=("Pobór wody z cieku pompą do nawadniania to usługa wodna – wymaga pozwolenia wodnoprawnego. "
             "Wniosek złóż przed sezonem: procedura trwa od kilku miesięcy do ponad roku.") + where))

    # 7. nawadnianie ze studni
    facts = []
    if limit_mm is not None:
        dose_m3 = 20 * area_ha * 10
        facts.append(f"jedno podlanie dawką 20 mm na {area_ha:.2f} ha to ok. {dose_m3:.0f} m³ wody "
                     f"(limit zwykłego korzystania: 1825 m³ na cały rok)")
    hints.append(LegalHint(
        topic="nawadnianie", title="Nawadnianie upraw wodą ze studni", requirement="pozwolenie wodnoprawne",
        group="permit", procedure_id="pozwolenie_wodnoprawne",
        legal_ids=["nawadnianie_pozwolenie", "zwykle_korzystanie", "studnia_do_30m", "studnia_glebinowa"],
        status="OK", sources=src("nawadnianie_pozwolenie", "zwykle_korzystanie"), fee_pln=fee, fee_year=fy,
        facts_used=facts,
        why=("Nawadnianie gruntów i upraw to szczególne korzystanie z wód – wymaga pozwolenia wodnoprawnego; "
             "nawadnianie deszczownią wodą podziemną zawsze wykracza poza zwykłe korzystanie. "
             "Wyjątek dla małego poboru (≤5 m³/d średnio w roku, studnia ≤30 m) przy uprawach towarowych "
             "jest niejednoznaczny – potwierdź w Nadzorze Wodnym.")))

    # 8. korzystanie z istniejącego zbiornika lub rowu
    hints.append(LegalHint(
        topic="istniejący zbiornik", title="Pobór wody z istniejącego stawu, zbiornika lub rowu",
        requirement="zależy od ilości wody i celu", group="depends", procedure_id="pozwolenie_wodnoprawne",
        legal_ids=["zwykle_korzystanie", "nawadnianie_pozwolenie", "row_zatrzymanie"], status="DO_WERYFIKACJI",
        sources=src("zwykle_korzystanie", "nawadnianie_pozwolenie"), fee_pln=fee, fee_year=fy,
        facts_used=[f"najbliższy rów ok. {round(ditches[0]['distance_m'])} m"] if ditches else [],
        unchecked=list(unchecked_hydro),
        why=("Woda z własnego stawu na potrzeby gospodarstwa, do 5 m³/d średnio w roku – zwykłe korzystanie "
             "(bez zgód). Nawadnianie upraw wodą z rowu, cieku lub zbiornika – pozwolenie wodnoprawne. "
             "Samo zatrzymanie wody w rowie (zastawka) – bez formalności. Granice „powszechnego korzystania” "
             "z wód bez urządzeń technicznych są niejednoznaczne.")))

    if slope is not None and slope > 3:
        hints[0].facts_used.append(f"średni spadek {slope:.1f}° – zbiornik wymaga grobli; uwaga na spływ i erozję")
    return hints


class LegalContextConnector(Connector):
    key = "legal_context"; title = "Pozwolenia, procedury i dofinansowania"; category = "knowledge"
    uses_crop = True
    live_ttl_s = 6 * 3600
    cache_version = 2
    depends_on: ClassVar[tuple[str, ...]] = ("hydrology", "protected_areas", "terrain")

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        from app.services.profile import run_block  # import lokalny: unikamy cyklu registry ↔ profile

        deps = await asyncio.gather(*(run_block(k, ctx) for k in self.depends_on), return_exceptions=True)
        by_key = dict(zip(self.depends_on, deps))
        data = {k: _block_data(v) for k, v in by_key.items()}
        facts_checked = {
            DEP_LABEL[k]: (STATUS_PL.get(v.status.value, v.status.value) if not isinstance(v, BaseException)
                           else "błąd")
            for k, v in by_key.items()
        }
        hints = legal_hints(ctx, data["hydrology"], data["protected_areas"], data["terrain"])

        funding = []
        for f in loader.items("funding"):
            if not f.get("for_farmer") or f.get("active") is False:
                continue
            if "TUZ" in str(f.get("applies_to_land", "")) and ctx.crop not in (None, "", "tuz"):
                continue
            funding.append(f["id"])

        missing = [lbl for lbl, st in facts_checked.items() if st not in ("sprawdzono", "sprawdzono częściowo")]
        uncertainty = ["Informacja orientacyjna, nie porada prawna – ostateczną kwalifikację robi Nadzór Wodny / "
                       "Zarząd Zlewni Wód Polskich oraz starostwo."]
        if missing:
            uncertainty.append("Reguły policzono bez części faktów o działce: " + ", ".join(missing) +
                               ". Tych warunków nie sprawdziliśmy.")
        meta = loader.meta("legal_pl")
        prov = [_knowledge_prov("Prawo wodne – reguły (prawo_wodne.yaml)", meta.get("snapshot_date"),
                                notes=meta.get("basis")),
                _knowledge_prov("procedury i opłaty (procedures.yaml)", loader.meta("procedures").get("snapshot_date"),
                                notes=loader.meta("procedures").get("legal_text")),
                _knowledge_prov("dofinansowania (programs.yaml)", loader.meta("funding").get("snapshot_date"))]
        info = LegalContextInfo(hints=hints, funding_ids=funding, disclaimer=meta.get("disclaimer"),
                                facts_checked=facts_checked)
        status = BlockStatus.ok if not missing else BlockStatus.partial
        return self.block(status, data=info, provenance=prov, uncertainty=uncertainty)
