import httpx
import pytest
import respx

from app.connectors.hydrology import BDOT
from app.connectors.land_cover import PC_STAC, PC_STATS, LandCoverConnector
from tests.conftest import make_ctx

WC_STATS = {"properties": {"statistics": {"map_b1": {"histogram": [[10, 80, 10], [10, 40, 50]]}}}}


@respx.mock
async def test_land_cover_worldcover_shares():
    respx.post(PC_STAC).mock(return_value=httpx.Response(200, json={"features": [
        {"id": "ESA_WorldCover_10m_2021_v200_N51E015"}]}))
    respx.post(url__startswith=PC_STATS).mock(return_value=httpx.Response(200, json=WC_STATS))
    respx.get(url__startswith=BDOT).mock(return_value=httpx.Response(200, json={"features": []}))
    b = await LandCoverConnector().fetch(make_ctx())
    assert b.status.value == "ok"
    assert b.data.classes["grunty orne"] == 80.0 and b.data.cropland_share_pct == 80.0
    assert b.data.agricultural_share_pct == 80.0 and b.data.bdot_classes == {}


@respx.mock
async def test_land_cover_all_down():
    respx.post(PC_STAC).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=BDOT).mock(return_value=httpx.Response(503))
    b = await LandCoverConnector().fetch(make_ctx())
    assert b.status.value == "error"


@pytest.mark.live
async def test_live_land_cover_srodka():
    from datetime import date
    from app.connectors.uldk import resolve_by_id
    from app.contracts.models import AnalysisContext
    ctx = AnalysisContext(parcel=await resolve_by_id("302504_5.0019.52/16"), as_of=date(2024, 7, 1))
    b = await LandCoverConnector().fetch(ctx)
    assert b.data.cropland_share_pct > 80
