import httpx
import pytest
import respx
from datetime import date, timedelta

from app.connectors.uldk import _parse, looks_like_parcel_id
from app.contracts.models import DailySeries
from app.knowledge import loader
from app.science.et0 import et0_penman_monteith
from app.science.water_balance import season_summaries, window_vs_normal

ULDK_OK = ("0\nSRID=4326;POLYGON((21 52,21.001 52,21.001 52.001,21 52.001,21 52))"
           "|146505_8.0116.5|mazowieckie|powiat Warszawa|Warszawa (miasto)|1-01-16|5\n")


def test_uldk_parse():
    p = _parse(ULDK_OK)
    assert p.id == "146505_8.0116.5" and p.region_code == "0116" and p.parcel_number == "5"
    assert 0.5 < p.area_ha < 0.9


def test_uldk_parse_error():
    import pytest

    from app.connectors.uldk import ParcelNotFound
    with pytest.raises(ParcelNotFound):
        _parse("-1 brak wyników")


def test_parcel_id_regex():
    assert looks_like_parcel_id("141201_1.0001.123/4")
    assert not looks_like_parcel_id("Mokotów 5")


def test_et0_fao56_example():
    # FAO-56 przykład 18 (Bruksela, 6 lipca): ET0 ≈ 3.9 mm/d
    v = et0_penman_monteith(date(2024, 7, 6), 50.8, 100, 21.5, 12.3, (63 + 84) / 2, 2.078, 22.07)
    assert 3.3 < v < 4.5


def _series(days=4000, p=1.5, e=2.0):
    start = date(2015, 1, 1)
    ds = [start + timedelta(days=i) for i in range(days)]
    return DailySeries(dates=ds, precip_mm=[p] * days, tmax_c=[20] * days, tmin_c=[10] * days, et0_mm=[e] * days)


def test_water_balance_aggregates():
    s = _series()
    seasons = season_summaries(s)
    assert seasons and seasons[0].cwb_apr_sep_mm < 0
    assert seasons[0].longest_dry_spell_days == 0
    cur, norm = window_vs_normal(s, s.dates[-1], 30, "precip_mm")
    assert cur == 45.0 and norm == 45.0


def test_knowledge_collections_load():
    for name in loader.COLLECTIONS:
        data = loader.load(name)
        assert data.get("items"), name
        for it in data["items"]:
            assert "id" in it, (name, it)
    assert loader.get_item("crops", "kukurydza_ziarno")["sowing"].startswith("04")


@respx.mock
async def test_uldk_rate_limit_redirect_is_503_not_500(monkeypatch):
    """GUGiK przy limicie odsyła 302 na stronę zastępczą – ma być czytelny 503, nie wyjątek parsera geometrii."""
    import asyncio

    from fastapi import HTTPException

    from app.api.routes.parcel import _resolve
    from app.connectors.uldk import ULDK_URL

    async def no_sleep(_):
        return None
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    respx.get(url__startswith=ULDK_URL).mock(
        return_value=httpx.Response(302, headers={"Location": "https://integracja01.gugik.gov.pl/resp/uldk.php"}))
    with pytest.raises(HTTPException) as e:
        await _resolve("999999_9.9999.999", None, None)
    assert e.value.status_code == 503 and "ogranicza" in e.value.detail


def test_uldk_parse_bogus_geometry():
    from app.connectors.uldk import UldkLimited
    with pytest.raises(UldkLimited):
        _parse("0\n0101000020E6100000000000000080564000000000008056400101|302504_5.0019.52")


def test_tile_bbox_3857_world_and_quadrant():
    from app.api.routes.tiles import tile_bbox_3857
    w = tile_bbox_3857(0, 0, 0)
    assert abs(w[0] + 20037508.34) < 1 and abs(w[3] - 20037508.34) < 1
    q = tile_bbox_3857(1, 1, 0)          # prawa górna ćwiartka
    assert abs(q[0]) < 1e-6 and abs(q[1]) < 1e-6
