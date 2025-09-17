from fastapi import FastAPI
from server.middleware.otel import instrument_app
from server.middleware.trustops import attach_trustops
from server.middleware.redaction import attach_redaction
from .grounded import router as grounded_router
from .api import router as api_router

app = FastAPI(title="Universal App")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

instrument_app(app)
attach_trustops(app)
attach_redaction(app)

@app.get('/healthz')
def health():
    return {"ok": True}


app.include_router(api_router)
app.include_router(grounded_router)