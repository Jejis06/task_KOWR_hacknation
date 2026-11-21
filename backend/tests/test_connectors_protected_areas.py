import httpx
import pytest
import respx

from app.connectors.protected_areas import GDOS_WFS, LAYERS, ProtectedAreasConnector, _wkt_ne
from app.core.geo import to_2180
from tests.conftest import make_ctx


def test_wkt_axis_swapped():
    from shapely.geometry import shape
    g = to_2180(shape(make_ctx().parcel.geometry.model_dump()))
    first = _wkt_ne(g).split("((")[1].split(",")[0].split()
    assert float(first[0]) > 450_000 and float(first[1]) < 400_000   # N ≈ 482 tys., E ≈ 380 tys.


@respx.mock
async def test_protected_hits_and_nearby():
    def handler(request):
        q = dict(request.url.params)
        if q["TYPENAME"] == "GDOS:ObszarySpecjalnejOchrony" and q["CQL_FILTER"].startswith("INTERSECTS"):
            return httpx.Response(200, json={"features": [{"properties": {"nazwa": "Dolina", "kod": "PLB1"}}]})
        if q["TYPENAME"] == "GDOS:Rezerwaty" and q["CQL_FILTER"].startswith("DWITHIN"):
            return httpx.Response(200, json={"features": [{"properties": {"nazwa": "Rez"}}]})
        return httpx.Response(200, json={"features": []})
    respx.get(url__startswith=GDOS_WFS).mock(side_effect=handler)
    b = await ProtectedAreasConnector().fetch(make_ctx())
    assert b.status.value == "ok" and len(b.data.checked_layers) == len(LAYERS)
    assert b.data.hits[0].code == "PLB1" and b.data.hits[0].distance_m == 0
    assert b.data.nearby[0].name == "Rez"


@respx.mock
async def test_protected_down_is_error():
    respx.get(url__startswith=GDOS_WFS).mock(return_value=httpx.Response(503))
    b = await ProtectedAreasConnector().fetch(make_ctx())
    assert b.status.value == "error"


@pytest.mark.live
async def test_live_protected_narew():
    from datetime import date

    from app.connectors.uldk import resolve_by_id
    from app.contracts.models import AnalysisContext
    ctx = AnalysisContext(parcel=await resolve_by_id("200201_5.0011.599"), as_of=date(2024, 7, 1))
    b = await ProtectedAreasConnector().fetch(ctx)
    assert any(h.code == "PLB200001" for h in b.data.hits)
