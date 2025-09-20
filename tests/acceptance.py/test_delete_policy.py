from starlette.testclient import TestClient
from services.backend.app import app

client = TestClient(app)

def test_delete_requires_approval_header():
    # ייצור פריט רגיל
    r = client.post("/api/items", json={"name":"need-approval","description":"x"})
    iid = r.json()["id"]

    # בלי הכותרת -> 403
    r = client.delete(f"/api/items/{iid}")
    assert r.status_code == 403

    # עם הכותרת -> 200
    r = client.delete(f"/api/items/{iid}", headers={"X-Admin-Approval":"yes"})
    assert r.status_code == 200

def test_delete_forbidden_name():
    r = client.post("/api/items", json={"name":"protected","description":"x"})
    iid = r.json()["id"]
    r = client.delete(f"/api/items/{iid}", headers={"X-Admin-Approval":"yes"})
    assert r.status_code == 403
