# services/micro/catalog/app.py
from fastapi import FastAPI
app = FastAPI(title="catalog-svc")

@app.get("/healthz")
def health(): return {"ok": True, "svc": "catalog"}

@app.get("/api/ping")
def ping(): return {"pong": True}
