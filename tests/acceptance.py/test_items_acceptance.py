# tests/acceptance/test_items_acceptance.py
from starlette.testclient import TestClient
from services.backend.app import app

client = TestClient(app)

def test_items_crud_and_evidence():
    # create
    r = client.post("/api/items", json={"name": "acc", "description": "test"})
    assert r.status_code == 200
    item_id = r.json()["id"]

    # list
    r = client.get("/api/items")
    assert r.status_code == 200
    assert any(x.get("id") == item_id for x in r.json())

    # grounded demo (בלי NLI כבד, רק כיסוי וציטוטים)
    r = client.get("/grounded/demo?q=What%20are%20items%3F&src_text=Items%20are%20records")
    assert r.status_code == 200
    j = r.json()
    assert "coverage" in j and "citations" in j

    # delete
    r = client.delete(f"/api/items/{item_id}")
    assert r.status_code == 200
