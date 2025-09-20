# tests/acceptance.py/test_outbox_worker.py

from starlette.testclient import TestClient
from services.backend.app import app

client = TestClient(app)

def test_outbox_flush_marks_sent():
    # create + delete
    r = client.post("/api/items", json={"name":"tmp-del","description":"x"})
    assert r.status_code == 200
    item_id = r.json()["id"]

    r = client.delete(f"/api/items/{item_id}")
    assert r.status_code == 200

    # לפני flush – חייב להיות pending
    j = client.get("/api/debug/outbox").json()
    assert isinstance(j, list)
    assert any(row["action"]=="deleted" and row["status"]=="pending" for row in j)

    # flush -> sent
    r = client.post("/api/debug/outbox/flush")
    assert r.status_code == 200

    j = client.get("/api/debug/outbox").json()
    assert any(row["action"]=="deleted" and row["status"]=="sent" for row in j)
