from starlette.testclient import TestClient
from services.backend.app import app

client = TestClient(app)

def test_outbox_on_delete():
    # צור פריט
    r = client.post("/api/items", json={"name":"todel", "description":"x"})
    assert r.status_code == 200
    item_id = r.json()["id"]

    # מחיקה
    r = client.delete(f"/api/items/{item_id}")
    assert r.status_code == 200

    # וידוא outbox
    j = client.get("/api/debug/outbox").json()
    assert any(row["action"]=="deleted" and row["key"]==str(item_id) for row in j)
