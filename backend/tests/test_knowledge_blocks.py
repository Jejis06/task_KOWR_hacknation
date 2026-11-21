"""Bloki wiedzy (B): crop_calendar i legal_context – bez sieci."""
from datetime import date

import pytest

from app.contracts.models import AnalysisContext, BlockStatus, GeoJSONGeometry, ParcelRef
from app.knowledge import loader
from app.knowledge.blocks import crop_calendar, fee_for, legal_hints, parse_window, roman_months

PARCEL = ParcelRef(id="302504_5.0024.7", geometry=GeoJSONGeometry(type="Point", coordinates=[17.2, 52.22]),
                   centroid=(17.2, 52.22), bbox=(17.19, 52.21, 17.21, 52.23), area_ha=14.47)


def cal(d: date, crop: str | None):
    status, info, unc, msgs = crop_calendar(d, crop)
    return status, info


# ── pomocnicze ──
def test_parse_window_and_roman():
    assert parse_window("09-15..10-20", 2026) == (date(2026, 9, 15), date(2026, 10, 20))
    assert parse_window("sadzenie VIII–IX lub IV", 2026) is None
    assert parse_window(None, 2026) is None
    assert roman_months("kwitnienie i nalewanie ziarna (VI)") == {6}
    assert roman_months("strzelanie w źdźbło – kłoszenie (V–VI)") == {5, 6}


# ── kalendarz: 4 pory roku ──
def test_calendar_january_winter_wheat_dormant():
    status, i = cal(date(2026, 1, 15), "pszenica_ozima")
    assert status == BlockStatus.ok
    assert i.in_season_on_as_of is True
    assert i.current_stage == "spoczynek zimowy"
    assert i.sowing_ok_now is False
    names = [s.name for s in i.stages]
    assert names[0].startswith("siew") and "zbiór" in names
    # fazy FAO od ruszenia wegetacji wiosną 2026
    fao = [s for s in i.stages if s.name == "faza początkowa"][0]
    assert fao.start == date(2026, 3, 25) and fao.kc == 0.4


def test_calendar_april_maize_before_sowing_and_suggestions():
    status, i = cal(date(2026, 4, 10), "kukurydza_ziarno")
    assert i.in_season_on_as_of is False and i.current_stage == "przed siewem"
    assert i.sowing_ok_now is False
    assert any("za wcześnie" in w for w in i.warnings)
    # w kwietniu sieje się zboża jare / ziemniaki
    assert any("Ziemniak" in s for s in i.suggested_crops_now)


def test_calendar_july_maize_critical_period():
    status, i = cal(date(2026, 7, 15), "kukurydza_ziarno")
    assert i.in_season_on_as_of is True
    assert i.current_stage in ("rozwój roślin", "pełnia wzrostu")
    assert any("okres krytyczny" in w for w in i.warnings)
    mid = [s for s in i.stages if s.name == "pełnia wzrostu"][0]
    assert mid.kc == 1.2


def test_calendar_october_winter_wheat_sowing_ok():
    status, i = cal(date(2026, 10, 5), "pszenica_ozima")
    assert i.sowing_ok_now is True
    assert i.in_season_on_as_of is True  # kampania 2026/27 już trwa (siew od 15.09)
    assert any("termin siewu" in w for w in i.warnings)


def test_calendar_november_maize_too_late():
    status, i = cal(date(2026, 11, 21), "kukurydza_ziarno")
    assert i.sowing_ok_now is False and i.in_season_on_as_of is False
    w = " ".join(i.warnings)
    assert "Listopad" in w and "niemożliwy" in w and "130–160 dni" in w and "8 °C" in w
    # stages pokazują następny sezon
    assert i.stages[0].start.year == 2027


def test_calendar_without_crop():
    status, i = cal(date(2026, 7, 1), None)
    assert status == BlockStatus.ok and i.crop == "" and i.in_season_on_as_of is True
    status, i = cal(date(2026, 12, 1), None)
    assert i.in_season_on_as_of is False and any(w.startswith("Lis–lut") for w in i.warnings)


def test_calendar_unknown_crop():
    status, i, unc, msgs = crop_calendar(date(2026, 7, 1), "banan")
    assert status == BlockStatus.no_data and i is None and msgs


@pytest.mark.parametrize("crop", [c["id"] for c in loader.items("crops")])
@pytest.mark.parametrize("d", [date(2026, 1, 10), date(2026, 4, 15), date(2026, 7, 15), date(2026, 10, 15)])
def test_calendar_every_crop_every_season(crop, d):
    status, i = cal(d, crop)
    assert status == BlockStatus.ok
    assert i.current_stage
    for s in i.stages:
        assert s.start <= s.end


# ── prawo ──
def ctx(d=date(2026, 7, 1)):
    return AnalysisContext(parcel=PARCEL, as_of=d, crop="ziemniak")


def test_legal_without_facts_lists_unchecked():
    hints = legal_hints(ctx(), None, None, None)
    topics = {h.topic for h in hints}
    assert {"staw", "oczko", "rów", "studnia", "nawadnianie", "istniejący zbiornik"} <= topics
    staw = hints[0]
    assert staw.group == "notification" and staw.procedure_id == "zgloszenie_wodnoprawne"
    assert staw.unchecked and any("powodzi" in u for u in staw.unchecked)
    assert all(h.why for h in hints)
    # nigdy „na pewno nie potrzebujesz zgody”
    assert not any("na pewno" in h.why.lower() for h in hints)


def test_legal_flood_zone_natura_and_ditch():
    hydro = {"in_flood_zone": "1%", "flood_zone_checked": True,
             "nearest_water": [{"kind": "ditch", "name": "R-12", "distance_m": 85.0},
                               {"kind": "river", "name": "Warta", "distance_m": 1500.0}],
             "groundwater_depth_m": "2–5 m", "water_management_board": "NW Środa Wlkp."}
    prot = {"hits": [{"kind": "Natura 2000 OSO", "name": "Dolina Warty", "code": "PLB300002"}]}
    terr = {"position": "depression", "position_label_pl": "zagłębienie (dołek)",
            "depressions_geojson": {"type": "FeatureCollection", "features": [{}, {}]}, "slope_mean_deg": 1.0}
    hints = legal_hints(ctx(), hydro, prot, terr)
    staw = hints[0]
    assert staw.group == "depends" and "powodzi" in staw.caution and "RDOŚ" in staw.caution
    assert not staw.unchecked
    row = next(h for h in hints if h.topic == "rów")
    assert "200 m" in row.why and any("85 m" in f for f in row.facts_used)
    river = next(h for h in hints if h.title.startswith("Nawadnianie wodą z rzeki"))
    assert any("Warta" in f for f in river.facts_used)
    assert "NW Środa Wlkp." in staw.why


def test_fee_follows_analysis_year():
    assert fee_for("zgloszenie_wodnoprawne", 2026) == (132.33, 2026)
    assert fee_for("pozwolenie_wodnoprawne", 2027) == (341.95, 2027)
    # starsze lata: brak stawki w bazie → najbliższa znana z jawnym rokiem
    fee, year = fee_for("pozwolenie_wodnoprawne", 2019)
    assert year == 2026 and fee == 330.07


def test_well_limit_in_mm_uses_parcel_area():
    hints = legal_hints(ctx(), None, None, None)
    well = next(h for h in hints if h.title.startswith("Studnia do 30 m"))
    assert any("1825 m³/rok" in f and "14.47 ha" in f for f in well.facts_used)


# ── spójność referencji w YAML ──
def test_yaml_references_are_consistent():
    procedures = {p["id"] for p in loader.items("procedures")}
    legal = {r["id"] for r in loader.items("legal_pl")}
    funding = {f["id"] for f in loader.items("funding")}
    measures = {m["id"] for m in loader.items("measures")}
    for r in loader.items("legal_pl"):
        if r.get("procedure_id"):
            assert r["procedure_id"] in procedures, r["id"]
    for m in loader.items("measures"):
        for lid in m.get("legal_ids", []):
            assert lid in legal, (m["id"], lid)
        for fid in m.get("funding", []):
            assert fid in funding, (m["id"], fid)
    for f in loader.items("funding"):
        for mid in f.get("measures", []):
            assert mid in measures, (f["id"], mid)
    # reguły z bloku też wskazują istniejące wpisy
    for h in legal_hints(ctx(), None, None, None):
        assert h.procedure_id is None or h.procedure_id in procedures
        assert all(lid in legal for lid in h.legal_ids)
    smsr = set(loader.meta("crops")["smsr_groups"])
    for c in loader.items("crops"):
        g = c.get("smsr_group") or ""
        assert g in smsr or g.startswith("nie dotyczy"), (c["id"], g)


def test_new_crops_present():
    ids = {c["id"] for c in loader.items("crops")}
    assert {"pszenzyto_ozime", "jeczmien_ozimy", "owies"} <= ids


# ── kontrakt wyników analizy (blok `analysis`, propozycja B dla A) ──
def test_analysis_contract_example_validates():
    from app.contracts.models import AnalysisResult
    example = {
        "assessment": {"current_level": "moderate", "historical_level": "high", "critical_months": [5, 6, 7],
                       "drought_years": [2019, 2022], "confidence": "medium",
                       "evidence": [{"text": "KBW 60 dni: −44 mm (norma −25 mm)", "block": "weather_history"}]},
        "causes": [{"key": "opady_deficyt", "label_pl": "Za mało opadów", "share": 0.55, "evidence": []}],
        "recommendations": [{"measure_id": "zastawka_row", "group": "retencja_krajobrazowa", "title": "Zastawka",
                             "why": "rów 140 m", "legal_ids": ["row_zatrzymanie"]}],
        "irrigation": {"recommended": "no", "horizon_days": 16, "evidence": []},
    }
    r = AnalysisResult.model_validate(example)
    assert r.assessment.current_level == "moderate" and r.recommendations[0].priority == 1
    # measure_id i legal_ids muszą wskazywać istniejące wpisy bazy wiedzy
    measures = {m["id"] for m in loader.items("measures")}
    legal = {x["id"] for x in loader.items("legal_pl")}
    causes = set(loader.meta("measures")["cause_keys"])
    assert r.recommendations[0].measure_id in measures
    assert set(r.recommendations[0].legal_ids) <= legal
    assert r.causes[0].key in causes
