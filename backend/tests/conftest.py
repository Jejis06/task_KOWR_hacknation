import pytest

from app.contracts.models import AnalysisContext, GeoJSONGeometry, ParcelRef


@pytest.fixture(autouse=True)
def _fresh_http_client():
    """Każdy test dostaje świeży klient httpx (respx mockuje transport per test)."""
    import app.core.http as h
    h._client = None
    yield
    h._client = None


def make_ctx(as_of="2024-07-15", crop="pszenica_ozima", lon=17.2525, lat=52.199, d=0.004):
    from datetime import date
    ring = [[lon - d, lat - d / 2], [lon + d, lat - d / 2], [lon + d, lat + d / 2], [lon - d, lat + d / 2],
            [lon - d, lat - d / 2]]
    p = ParcelRef(id="302504_5.0019.52/16", voivodeship="wielkopolskie", county="powiat średzki",
                  commune="Środa Wielkopolska", geometry=GeoJSONGeometry(type="Polygon", coordinates=[ring]),
                  centroid=(lon, lat), bbox=(lon - d, lat - d / 2, lon + d, lat + d / 2), area_ha=12.0)
    return AnalysisContext(parcel=p, as_of=date.fromisoformat(as_of), crop=crop)
