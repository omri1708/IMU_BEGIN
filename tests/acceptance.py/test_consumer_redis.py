import os, pathlib, json, time, pytest
from starlette.testclient import TestClient
from services.backend.app import app

REDIS_URL = os.getenv("REDIS_URL")

@pytest.mark.skipif(not REDIS_URL, reason="REDIS_URL not set; skipping Redis consumer test")
def test_consumer_items_deleted(client: TestClient = TestClient(app)):
    # 1) צור+מחק פריט, עשה flush → outbox → bus
    r = client.post("/api/items", json={"name":"bus-check","description":"x"})
    iid = r.json()["id"]
    client.delete(f"/api/items/{iid}", headers={"X-Admin-Approval":"yes"})
    client.post("/api/debug/outbox/flush")

    # 2) הרץ צרכן פעם אחת
    from services.eventing.redis_consumer import consume_once
    n = consume_once(stream="items-deleted", group="imu", consumer="test", max_n=100)
    assert n >= 1

    # 3) קובץ ה-sink צריך לכלול את האירוע
    p = pathlib.Path(".imu_runs/sink_items-deleted.jsonl")
    assert p.exists()
    lines = [json.loads(ln) for ln in p.read_text(encoding="utf-8").strip().splitlines()]
    # לפחות אחת מהרשומות עם item_id == iid
    assert any(int(row.get("item_id", -1)) == int(iid) for row in lines)
