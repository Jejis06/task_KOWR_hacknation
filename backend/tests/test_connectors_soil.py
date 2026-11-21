import httpx
import pytest
import respx
from shapely.geometry import shape

from app.connectors.soil import IUNG_WMS, MGR_WMS, SOILGRIDS, SoilConnector, saxton_rawls_taw_mm
from app.core.geo import sample_points_2180, to_2180
from tests.conftest import make_ctx

MGR_XML = ('<?xml version="1.0" encoding="UTF-8"?><FeatureInfoResponse xmlns="http://www.esri.com/wms">'
           '<FIELDS KOMPLEKS_NR="1" TYPPODTYP_NR="D" PODLOZE1="pgm" PODLOZE2="Null" PODLOZE3="gl" '
           'TERENZALEWOWY="false"></FIELDS></FeatureInfoResponse>')
IUNG_JSON = {"type": "FeatureCollection", "features": [{"properties": {"GRAY_INDEX": 2}}]}
SG_JSON = {"properties": {"layers": [
    {"name": n, "unit_measure": {"d_factor": 10}, "depths": [
        {"label": lab, "values": {"mean": v}} for lab in ("0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm")]}
    for n, v in (("clay", 110), ("sand", 700), ("silt", 190), ("soc", 190))]}}


def test_sample_points_inside():
    ctx = make_ctx()
    g = shape(ctx.parcel.geometry.model_dump())
    pts = sample_points_2180(g, 5)
    assert len(pts) == 5
    from shapely.geometry import Point
    assert all(to_2180(g).contains(Point(p)) for p in pts)


def test_saxton_rawls_reasonable():
    # 1 m piasku gliniastego ~ 80–160 mm; gliny pylastej ~ 150–250 mm
    sandy = saxton_rawls_taw_mm([(1000, 0.75, 0.08, 1.5)])
    loam = saxton_rawls_taw_mm([(1000, 0.25, 0.20, 2.0)])
    assert 50 < sandy < loam < 300


@respx.mock
async def test_soil_iung_and_mgr():
    respx.get(url__startswith=IUNG_WMS).mock(return_value=httpx.Response(200, json=IUNG_JSON))
    respx.get(url__startswith=MGR_WMS).mock(return_value=httpx.Response(200, text=MGR_XML))
    respx.get(url__startswith=SOILGRIDS).mock(return_value=httpx.Response(200, json=SG_JSON))
    b = await SoilConnector().fetch(make_ctx())
    assert b.status.value == "ok"
    d = b.data
    assert d.drought_category == 2 and d.awc_mm == 150
    assert d.agri_complex.startswith("pszenny bardzo dobry") and "czarne ziemie" in d.soil_type
    assert d.texture_profile == ["pgm", "gl"] and d.clay_pct == 11.0
    assert any("SZACUNEK" in u for u in b.uncertainty)


@respx.mock
async def test_soil_fallback_soilgrids_only():
    respx.get(url__startswith=IUNG_WMS).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=MGR_WMS).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=SOILGRIDS).mock(return_value=httpx.Response(200, json=SG_JSON))
    b = await SoilConnector().fetch(make_ctx())
    assert b.status.value == "partial" and b.data.source_used == "soilgrids"
    assert b.data.awc_mm and b.data.drought_category is None


@respx.mock
async def test_soil_all_down_is_error():
    respx.get(url__startswith=IUNG_WMS).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=MGR_WMS).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=SOILGRIDS).mock(return_value=httpx.Response(503))
    b = await SoilConnector().fetch(make_ctx())
    assert b.status.value == "error" and b.data is None


@pytest.mark.live
async def test_live_soil_wielkopolska():
    from app.connectors.uldk import resolve_by_id
    from app.contracts.models import AnalysisContext
    from datetime import date
    ctx = AnalysisContext(parcel=await resolve_by_id("302504_5.0019.52/16"), as_of=date(2024, 7, 1))
    b = await SoilConnector().fetch(ctx)
    assert b.status.value == "ok" and b.data.drought_category == 2
