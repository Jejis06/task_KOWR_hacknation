import httpx
import numpy as np
import pytest
import respx

from app.connectors.hydrology import BDOT, CBDH, GZWP, ISOK_WMS, JCWPD, PODTOP, HydrologyConnector
from tests.conftest import make_ctx


def _png(rgb=(255, 0, 0), alpha=255, w=50, h=50) -> bytes:
    from rasterio.io import MemoryFile
    arr = np.zeros((4, h, w), dtype="uint8")
    arr[0], arr[1], arr[2], arr[3] = rgb[0], rgb[1], rgb[2], alpha
    with MemoryFile() as mf:
        with mf.open(driver="PNG", width=w, height=h, count=4, dtype="uint8") as ds:
            ds.write(arr)
        return mf.read()


def _mock_pig(e0=380606, n0=482875):
    ditch = {"features": [{"attributes": {"X_KOD": "SWRM02"},
                           "geometry": {"paths": [[[e0 + 400, n0 - 300], [e0 + 400, n0 + 300]]]}}]}
    empty = {"features": []}
    respx.get(url__regex=rf"{BDOT}/32/query.*").mock(return_value=httpx.Response(200, json=ditch))
    respx.get(url__regex=rf"{BDOT}/\d+/query.*").mock(return_value=httpx.Response(200, json=empty))
    bore = {"features": [{"attributes": {"NAZWA": "otwór 1", "GLEBOKOSC": 25.0, "DATA_WYKONANIA": "1975",
                                         "TYP_OTWORU": "Otwór", "ZLIKWIDOWANY": "Nie"},
                          "geometry": {"x": e0 + 900, "y": n0}}]}
    respx.get(url__startswith=f"{CBDH}/0/query").mock(return_value=httpx.Response(200, json=bore))
    respx.get(url__startswith=f"{GZWP}/identify").mock(return_value=httpx.Response(200, json={"results": [
        {"layerId": 0, "attributes": {"Nr GZWP": "143", "Nazwa GZWP": "Subzbiornik", "Typ ośrodka": "porowy",
                                      "Głębokość średnia [m]": "120"}}]}))
    respx.get(url__startswith=f"{JCWPD}/identify").mock(return_value=httpx.Response(200, json={"results": [
        {"layerId": 2, "attributes": {"Kod UE": "PLGW600061", "Region wodny": "Warty", "Dorzecze": "Odra"}}]}))
    respx.get(url__startswith=f"{PODTOP}/identify").mock(return_value=httpx.Response(200, json={"results": []}))


@respx.mock
async def test_hydrology_flood_10pct_and_waters():
    respx.get(url__startswith=ISOK_WMS).mock(
        return_value=httpx.Response(200, content=_png((255, 0, 0)), headers={"content-type": "image/png"}))
    _mock_pig()
    b = await HydrologyConnector().fetch(make_ctx())
    d = b.data
    assert b.status.value == "ok", b.messages
    assert d.in_flood_zone == "10%" and d.in_flood_hazard_area and d.flood_zone_checked
    assert d.nearest_water and d.nearest_water[0].kind == "ditch"
    assert d.nearest_boreholes[0]["depth_m"] == 25.0
    assert "RZGW w Poznaniu" in d.water_management_board and d.jcwpd_code == "PLGW600061"
    assert d.groundwater_depth_m is None and any("MHP" in u or "Hydrogeologiczna" in u for u in b.uncertainty)


@respx.mock
async def test_hydrology_no_flood_transparent():
    respx.get(url__startswith=ISOK_WMS).mock(
        return_value=httpx.Response(200, content=_png(alpha=0), headers={"content-type": "image/png"}))
    _mock_pig()
    b = await HydrologyConnector().fetch(make_ctx())
    assert b.data.in_flood_zone is None and b.data.in_flood_hazard_area is False


@respx.mock
async def test_hydrology_isok_down_partial():
    respx.get(url__startswith=ISOK_WMS).mock(return_value=httpx.Response(503))
    _mock_pig()
    b = await HydrologyConnector().fetch(make_ctx())
    assert b.data.flood_zone_checked is False and any("ISOK" in m for m in b.messages)


@pytest.mark.live
async def test_live_hydrology_vistula_flood():
    from datetime import date

    from app.connectors.uldk import resolve_by_id
    from app.contracts.models import AnalysisContext
    ctx = AnalysisContext(parcel=await resolve_by_id("040402_2.0012.316/4"), as_of=date(2024, 7, 1))
    b = await HydrologyConnector().fetch(ctx)
    assert b.data.in_flood_zone in ("10%", "1%", "0.2%") and b.data.nearest_water
