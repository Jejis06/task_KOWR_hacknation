from fastapi.testclient import TestClient

from app.connectors.registry import BLOCKS
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_blocks_listed():
    keys = {b["key"] for b in client.get("/api/parcel/blocks").json()}
    assert keys == set(BLOCKS)


def test_knowledge_endpoint():
    r = client.get("/api/knowledge/procedures/zgloszenie_wodnoprawne")
    assert r.status_code == 200 and r.json()["deadlines"]["organ_objection_days"] == 30


def test_future_date_rejected():
    r = client.get("/api/parcel/profile", params={"id": "146505_8.0116.5", "date": "2999-01-01"})
    assert r.status_code == 422
