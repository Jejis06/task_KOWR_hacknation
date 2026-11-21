from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.connectors.yields import YieldsConnector, peak_ndvi_index
from app.contracts.models import BlockStatus, DataBlock, VegetationInfo, VegetationObs
from tests.conftest import make_ctx

BDL_VOIV = {"results": [{"name": "WIELKOPOLSKIE", "values": [{"year": "2022", "val": 55.3}, {"year": "2023", "val": 57.1}]},
                        {"name": "MAZOWIECKIE", "values": [{"year": "2023", "val": 50.0}]}]}
BDL_PL = {"results": [{"name": "POLSKA", "values": [{"year": "2023", "val": 53.8}]}]}


def _veg():
    s = [VegetationObs(date=date(y, 6, 15), ndvi=v) for y, v in ((2020, 0.8), (2021, 0.6), (2022, 0.7))]
    return VegetationInfo(series=s)


def test_peak_index():
    idx = peak_ndvi_index(_veg())
    assert [r["rel_index"] for r in idx] == [1.14, 0.86, 1.0]


@respx.mock
async def test_yields_connector():
    def handler(request):
        return httpx.Response(200, json=BDL_VOIV if request.url.params["unit-level"] == "2" else BDL_PL)
    respx.get(url__startswith="https://bdl.stat.gov.pl").mock(side_effect=handler)
    veg_block = DataBlock(key="vegetation", title="v", status=BlockStatus.ok, data=_veg())
    with patch("app.services.profile.run_block", AsyncMock(return_value=veg_block)):
        b = await YieldsConnector().fetch(make_ctx(as_of="2024-07-15"))
    voiv = [r for r in b.data.official if r.level == "voivodeship"]
    assert b.status.value == "ok" and [r.yield_t_ha for r in voiv] == [5.53, 5.71]
    assert all(r.year < 2024 for r in b.data.official) and b.data.parcel_productivity_index
    assert "województwa" in b.data.note


@pytest.mark.live
async def test_live_bdl_wheat():
    from app.connectors.yields import bdl_series
    res = await bdl_series(4332, 2, [2022, 2023])
    assert any(u["name"].upper() == "WIELKOPOLSKIE" for u in res)
