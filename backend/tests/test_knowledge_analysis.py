"""Blok analysis (B): ocena → przyczyny → rekomendacje → nawadnianie – na syntetycznych danych, bez sieci."""
from datetime import date

from app.contracts.models import AnalysisContext, GeoJSONGeometry, ParcelRef
from app.knowledge import loader
from app.knowledge.analysis import analyse_all
from app.knowledge.blocks import crop_calendar, legal_hints

PARCEL = ParcelRef(id="302504_5.0024.7", geometry=GeoJSONGeometry(type="Point", coordinates=[17.2, 52.22]),
                   centroid=(17.2, 52.22), bbox=(17.19, 52.21, 17.21, 52.23), area_ha=14.47)


def ctx(d=date(2026, 7, 10), crop="kukurydza_ziarno"):
    return AnalysisContext(parcel=PARCEL, as_of=d, crop=crop)


def _dry_daily(as_of: date) -> dict:
    """Suchy sezon: od 1 kwietnia opad 2 mm co 6 dni, ET0 4 mm/d."""
    days = [date.fromordinal(o) for o in range(date(as_of.year, 4, 1).toordinal(), as_of.toordinal() + 1)]
    return {"dates": [d.isoformat() for d in days], "precip_mm": [2.0 if i % 6 == 0 else 0.0 for i in range(len(days))],
            "et0_mm": [4.0] * len(days)}


def dry_data(c: AnalysisContext) -> dict:
    _, cal, _, _ = crop_calendar(c.as_of, c.crop)
    dep = {"type": "Feature", "properties": {"area_m2": 2400, "max_depth_m": 0.6, "volume_m3": 700, "touches_parcel": True},
           "geometry": {"type": "Polygon", "coordinates": [[[17.2, 52.22], [17.201, 52.22], [17.201, 52.221], [17.2, 52.22]]]}}
    return {
        "weather_history": {"cwb_60d_mm": -140, "cwb_60d_normal_mm": -60, "last_30d_precip_mm": 12, "last_30d_precip_normal_mm": 60,
                            "seasons": [{"year": y, "cwb_apr_sep_mm": v, "longest_dry_spell_days": 15}
                                        for y, v in zip(range(2017, 2027), [-300, -420, -380, -250, -310, -520, -400, -280, -350, -450])],
                            "monthly_climatology": [{"month": m, "cwb_mean_mm": -10 * m} for m in range(1, 13)],
                            "daily": _dry_daily(c.as_of)},
        "weather_forecast": {"dates": [f"2026-07-{d:02d}" for d in range(10, 26)], "precip_mm": [0] * 16, "et0_mm": [4.5] * 16},
        "drought": {"current": [{"source": "computed", "class_label": "susza – KBW −180 mm poniżej progu −150 mm"}],
                    "drought_years": [2018, 2019, 2022, 2023, 2026],
                    "periods": [{"drought": True, "end": "2026-06-30"}, {"drought": True, "end": "2023-07-10"}]},
        "soil": {"drought_category": 2, "awc_mm": 110, "soc_g_kg": 8},
        "terrain": {"slope_mean_deg": 3.5, "position": "mid_slope", "position_label_pl": "stok",
                    "depressions_geojson": {"type": "FeatureCollection", "features": [dep]},
                    "flow_lines_geojson": {"type": "FeatureCollection", "features": [{"properties": {"crosses_parcel": True}}]}},
        "hydrology": {"nearest_water": [{"kind": "ditch", "name": "R-7", "distance_m": 140}], "in_flood_zone": None,
                      "flood_zone_checked": True},
        "vegetation": {"anomaly": -0.15, "in_growing_season": True},
        "land_cover": {"classes": {"grunty orne": 95}},
        "protected_areas": {"hits": []},
        "crop_calendar": cal.model_dump(mode="json"),
    }


def test_dry_summer_full_chain():
    c = ctx()
    r = analyse_all(c, dry_data(c))
    a = r.assessment
    assert a.current_level in ("high", "very_high") and a.historical_level in ("high", "very_high")
    assert a.evidence and all(e.text and e.block for e in a.evidence)
    assert {x.key for x in r.causes} >= {"opady_deficyt", "gleba_niska_retencja", "odplyw_powierzchniowy", "uprawa_wrazliwa"}
    assert abs(sum(x.share for x in r.causes) - 1) < 0.05
    ids = [x.measure_id for x in r.recommendations]
    assert "zastawka_row" in ids and "oczko_zbiornik" in ids and "uprawa_w_poprzek_stoku" in ids
    oczko = next(x for x in r.recommendations if x.measure_id == "oczko_zbiornik")
    assert oczko.where_geojson and "staw_zgloszenie" in oczko.legal_ids
    irr = r.irrigation
    assert irr.recommended == "yes" and 10 <= irr.dose_mm <= 35
    assert irr.depletion_mm > irr.raw_mm and irr.ks < 1 and irr.soil_water   # FAO-56 rozdz. 8: stres wodny
    assert irr.yield_loss_pct and irr.yield_loss_pct > 0                     # równ. 90 z Ky kukurydzy
    assert r.water_balance and r.water_balance["season_deficit_m3"] > 0
    assert "nie wystąpiła" not in a.historical_summary
    # odwołania do bazy wiedzy istnieją
    measures = {m["id"] for m in loader.items("measures")}
    assert all(x.measure_id in measures for x in r.recommendations)
    assert all(x.key in loader.meta("measures")["cause_keys"] for x in r.causes)


def test_no_assessment_without_weather_and_drought():
    c = ctx()
    d = dry_data(c)
    d["weather_history"] = None
    d["drought"] = None
    r = analyse_all(c, d)
    assert r.assessment is None and not r.recommendations and not r.causes


def test_winter_no_irrigation_and_capped_level():
    c = ctx(d=date(2026, 11, 21))
    d = dry_data(c)
    r = analyse_all(c, d)
    assert r.irrigation.recommended == "no"
    assert r.assessment.current_level in ("none", "low", "moderate")


def test_flood_zone_blocks_pond():
    c = ctx()
    d = dry_data(c)
    d["hydrology"]["in_flood_zone"] = "1%"
    ids = [x.measure_id for x in analyse_all(c, d).recommendations]
    assert "oczko_zbiornik" not in ids


def test_national_park_no_infrastructure():
    c = ctx()
    d = dry_data(c)
    d["protected_areas"] = {"hits": [{"kind": "park narodowy", "name": "Wielkopolski PN", "distance_m": 0}]}
    r = analyse_all(c, d)
    groups = {x.group for x in r.recommendations}
    assert "retencja_krajobrazowa" not in groups and "agrotechnika" in groups
    assert any("park" in x.lower() for x in r.limitations)
    hints = legal_hints(c, d["hydrology"], d["protected_areas"], d["terrain"])
    topics = [h.topic for h in hints]
    assert topics[0] == "obszar chroniony" and "staw" not in topics and "studnia" not in topics


def test_cucumber_and_cabbage_in_crops():
    ids = {x["id"] for x in loader.items("crops")}
    assert {"ogorek", "kapusta"} <= ids


def test_drought_years_window_is_ten_seasons():
    c = ctx(d=date(2025, 7, 15))
    d = dry_data(c)
    d["drought"]["drought_years"] = [2015, 2019]
    a = analyse_all(c, d).assessment
    assert a.drought_years == [2019]
    assert any("1 z 10" in e.text for e in a.evidence)


def test_zero_drought_seasons_wording():
    c = ctx()
    d = dry_data(c)
    d["drought"] = {"current": [], "drought_years": [], "periods": []}
    a = analyse_all(c, d).assessment
    assert "nie wystąpiła tu w żadnym sezonie" in a.historical_summary


def test_kbw_ndmi_field_check():
    c = ctx()
    d = dry_data(c)
    d["vegetation"] = {"anomaly": -0.12, "ndmi_anomaly": -0.09, "in_growing_season": True}
    assert analyse_all(c, d).assessment.field_check["case"] == "confirmed"
    d["weather_history"] = {**d["weather_history"], "cwb_60d_mm": -60, "cwb_60d_normal_mm": -60}
    assert analyse_all(c, d).assessment.field_check["case"] == "local_problem"
