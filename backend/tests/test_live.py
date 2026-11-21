"""Testy na prawdziwych API – uruchom: uv run pytest -m live"""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.live
client = TestClient(app)


def test_live_resolve_by_id():
    r = client.get("/api/parcel/resolve", params={"id": "146505_8.0116.5"})
    assert r.status_code == 200 and r.json()["commune"]


def test_live_weather_history_under_budget():
    t0 = time.time()
    r = client.get("/api/parcel/block/weather_history",
                   params={"id": "146505_8.0116.5", "date": "2023-07-15", "no_cache": True})
    assert r.status_code == 200
    b = r.json()
    assert b["status"] in ("ok", "partial"), b["messages"]
    assert b["data"]["end"] <= "2023-07-15"          # brak „podglądania przyszłości”
    assert time.time() - t0 < 30
