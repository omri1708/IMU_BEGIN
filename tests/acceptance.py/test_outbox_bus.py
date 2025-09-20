# tests/acceptance.py/test_outbox_bus.py
import json, pathlib

def test_outbox_flush_writes_bus_file(client, tmp_path, monkeypatch):
    # ננתב את תיקיית ה-.imu_runs זמנית (אופציונלי)
    monkeypatch.chdir(tmp_path)
    p = pathlib.Path(".imu_runs/bus_items-deleted.jsonl")

    r = client.post("/api/items", json={"name":"xx","description":"x"})
    iid = r.json()["id"]
    client.delete(f"/api/items/{iid}", headers={"X-Admin-Approval":"yes"})

    client.post("/api/debug/outbox/flush")
    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert any('"action": "deleted"' in ln for ln in lines)
