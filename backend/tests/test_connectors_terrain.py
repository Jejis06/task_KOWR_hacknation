import httpx
import numpy as np
import pytest
import respx

from app.connectors.terrain import NMT_POINTS, TerrainConnector, grid_spec, parse_heights, snapped_grid
from app.science import terrain as T
from tests.conftest import make_ctx


def _grid(n=41, cell=10.0):
    c = (n - 1) / 2
    r, k = np.mgrid[0:n, 0:n]
    return r, k, c, cell


def test_priority_flood_fills_bowl():
    r, k, c, _ = _grid()
    z = 100 + 0.01 * ((r - c) ** 2 + (k - c) ** 2)       # misa – środek najniżej
    z[0, :] = z[-1, :] = z[:, 0] = z[:, -1] = 90           # brzeg niżej → misa bezodpływowa do brzegu
    filled = T.priority_flood(z)
    assert (filled - z)[20, 20] > 0.5


def test_d8_accumulation_on_plane_flows_south():
    r, _k, _c, _cell = _grid()
    z = 100 - 0.05 * r                                     # spadek na południe (wiersze rosną)
    fdir, acc = T.d8_accumulation(T.priority_flood(z, eps=1e-3))
    assert fdir[10, 10] == 4                               # S
    assert acc[-1, 20] >= 40                               # cała kolumna spływa do dolnego wiersza


def test_slope_and_aspect():
    r, _k, _c, cell = _grid()
    z = 100 - 0.1 * r * 1.0                                # 0.1 m na 10 m → ~0.57°, spadek na S
    slope, aspect = T.slope_aspect(z, cell)
    assert 0.4 < slope[20, 20] < 0.8 and abs(aspect[20, 20] - 180) < 1


def test_classify_position():
    assert T.classify_position(2.5, 1.0, 1.0, 0.0)[0] == "hilltop"
    assert T.classify_position(-2.5, 1.0, 1.0, 0.0)[0] == "depression"
    assert T.classify_position(0.0, 0.2, 0.5, 0.0)[0] == "flat"
    assert T.classify_position(0.0, 0.2, 4.0, 0.0)[0] == "mid_slope"
    assert T.classify_position(5.8, 8.0, 0.9, 0.0)[0] == "hilltop"


def test_parse_heights_and_grid_spec():
    assert parse_heights("1 2 85.2,1 3 ,1 4 -9999") == [85.2, None, None]
    cell, nr, nc = grid_spec((0, 0, 1000, 1000))
    assert nr * nc <= 7_500 and cell >= 5


def test_neighbouring_parcels_share_grid():
    """Sąsiednie działki: ten sam krok i węzły siatki w części wspólnej (spójne zagłębienia i spływy)."""
    a, ca, _, _ = snapped_grid((380_013.4, 482_101.7, 380_640.2, 482_733.9))
    b, cb, _, _ = snapped_grid((380_233.1, 482_090.2, 380_871.8, 482_741.3))
    assert ca == cb
    for v in (*a, *b):
        assert abs(v / ca - round(v / ca)) < 1e-9


@respx.mock
async def test_terrain_connector_hill():
    """Mock usługi: stożek – działka na szczycie → „górka”."""
    def handler(request):
        from urllib.parse import parse_qs
        lst = parse_qs(request.content.decode())["list"][0].split(",")
        cx, cy = 381_000, 482_880   # mniej więcej środek działki testowej w EPSG:2180 (E, N)
        out = []
        for t in lst:
            n, e = map(float, t.split())
            out.append(f"{t} {120 - 0.03 * ((e - cx) ** 2 + (n - cy) ** 2) ** 0.5:.1f}")
        return httpx.Response(200, text=",".join(out))
    respx.post(NMT_POINTS).mock(side_effect=handler)
    ctx = make_ctx(lon=17.2584, lat=52.1995, d=0.002)
    b = await TerrainConnector().fetch(ctx)
    assert b.status.value == "ok", b.messages
    assert b.data.position in ("hilltop", "upper_slope") and b.data.slope_mean_deg > 0.5
    assert b.data.flow_lines_geojson["type"] == "FeatureCollection"


@pytest.mark.live
async def test_live_terrain_lubelskie_slope():
    from datetime import date

    from app.connectors.uldk import resolve_by_id
    from app.contracts.models import AnalysisContext
    ctx = AnalysisContext(parcel=await resolve_by_id("060406_2.0136.AR_3.783/2"), as_of=date(2024, 7, 1))
    b = await TerrainConnector().fetch(ctx)
    assert b.status.value == "ok" and b.data.slope_mean_deg > 3
