def test_budget_status(client):
    r = client.get("/api/ops/budget/status")
    assert r.status_code == 200
    j = r.json()
    for k in ("day","day_cap","month","month_cap","ok"):
        assert k in j
