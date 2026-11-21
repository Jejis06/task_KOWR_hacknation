from datetime import date

import httpx
import pytest
import respx

from app.connectors.vegetation import (
    PC_STAC,
    PC_STATS,
    VegetationConnector,
    baseline_same_doy,
    boa_offset,
    expressions,
    parse_stats,
    pick_monthly,
)
from app.contracts.models import VegetationObs
from tests.conftest import make_ctx


def _item(i, d, cloud=5, base="05.10"):
    return {"id": f"S2_{i}", "properties": {"datetime": f"{d}T10:00:00Z", "eo:cloud_cover": cloud,
                                            "s2:processing_baseline": base}}


def test_offset_and_expression():
    assert boa_offset(_item(1, "2024-06-01")) == 1000 and boa_offset(_item(1, "2019-06-01", base="02.12")) == 0
    assert "2000.0" in expressions(1000, True) and "B11" in expressions(1000, True)


def test_parse_stats_masks_clouds():
    j = {"properties": {"statistics": {"c": {"sum": 80, "count": 100}, "n": {"sum": 60.0, "count": 100}}}}
    out = parse_stats(j)
    assert out["clear_frac"] == 0.8 and out["ndvi"] == 0.75
    cloudy = {"properties": {"statistics": {"c": {"sum": 10, "count": 100}, "n": {"sum": 5.0, "count": 100}}}}
    assert "ndvi" not in parse_stats(cloudy)


def test_pick_monthly_and_baseline():
    items = [_item(1, "2023-05-02", 40), _item(2, "2023-05-20", 3), _item(3, "2023-12-01", 1)]
    assert [i["id"] for i in pick_monthly(items)] == ["S2_2"]
    s = [VegetationObs(date=date(y, 6, 20), ndvi=0.7 + 0.01 * k) for k, y in enumerate((2020, 2021, 2022))]
    assert baseline_same_doy(s, date(2024, 6, 25)) == 0.71


@respx.mock
async def test_vegetation_connector_latest_and_series():
    def stac(request):
        import json
        body = json.loads(request.content)
        start = body["datetime"][:10]
        return httpx.Response(200, json={"features": [_item(start, start[:8] + "20")]})
    respx.post(PC_STAC).mock(side_effect=stac)
    respx.post(url__startswith=PC_STATS).mock(return_value=httpx.Response(200, json={"properties": {"statistics": {
        "c": {"sum": 95, "count": 100}, "n": {"sum": 66.5, "count": 100}, "m": {"sum": 28.5, "count": 100}}}}))
    b = await VegetationConnector().fetch(make_ctx(as_of="2024-07-15"))
    assert b.status.value in ("ok", "partial"), b.messages
    assert b.data.latest and b.data.latest.ndvi == 0.7 and b.data.latest.date <= date(2024, 7, 15)
    assert len(b.data.series) >= 5 and all(o.date <= date(2024, 7, 15) for o in b.data.series)


@respx.mock
async def test_vegetation_off_season_not_compared():
    respx.post(PC_STAC).mock(return_value=httpx.Response(200, json={"features": []}))
    b = await VegetationConnector().fetch(make_ctx(as_of="2024-12-15"))
    assert b.status.value == "not_applicable"


@pytest.mark.live
async def test_live_vegetation_srodka():
    from app.connectors.uldk import resolve_by_id
    from app.contracts.models import AnalysisContext
    ctx = AnalysisContext(parcel=await resolve_by_id("302504_5.0019.52/16"), as_of=date(2024, 7, 15))
    b = await VegetationConnector().fetch(ctx)
    assert b.data.latest and 0 < b.data.latest.ndvi < 1 and len(b.data.series) > 20
