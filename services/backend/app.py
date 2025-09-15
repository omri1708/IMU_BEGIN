from fastapi import FastAPI
from server.middleware.otel import instrument_app
from server.middleware.trustops import attach_trustops
from server.middleware.redaction import attach_redaction

app = FastAPI(title="Universal App")
instrument_app(app)
attach_trustops(app)
attach_redaction(app)

@app.get('/healthz')
def health():
    return {"ok": True}
from .api import router as api_router
app.include_router(api_router)
