from __future__ import annotations
from fastapi import FastAPI, Request
from typing import Callable
import yaml, json
from pathlib import Path
from grounded.evidence_gate import EvidenceGate
from alignment.attribution import compute_citations


def _load_policy():
    p = Path("policy/trustops.yaml")
    if not p.exists():
        return {"grounding": {"allow_domains": [], "nli_threshold": 0.72, "require_provenance": True}, "cost": {}}
    y = yaml.safe_load(p.read_text())
    g = y.get("grounding", {})
    return {"grounding": {"allow_domains": g.get("allow_domains", []),
                           "nli_threshold": g.get("nli_threshold", 0.72),
                           "require_provenance": g.get("require_provenance", True)},
            "cost": y.get("cost", {})}


def attach_trustops(app: FastAPI) -> None:
    pol = _load_policy()
    gate = EvidenceGate(pol["grounding"].get("allow_domains", []),
                        pol["grounding"].get("nli_threshold", 0.72),
                        pol["grounding"].get("require_provenance", True))

    @app.middleware("http")
    async def _evidence(request: Request, call_next: Callable):
        resp = await call_next(request)
        try:
            if resp.media_type == "application/json":
                body = b"".join([chunk async for chunk in resp.body_iterator])
                data = json.loads(body.decode("utf-8")) if body else {}
                # Evidence enforcement
                if isinstance(data, dict) and ("sources" in data or pol["grounding"].get("require_provenance", True)):
                    res = gate.check(data)
                    if not res.get("ok"):
                        from starlette.responses import JSONResponse
                        return JSONResponse({"error": "EvidenceGate", "details": res}, status_code=412)
                # Citations (provider-agnostic)
                if isinstance(data, dict) and data.get('answer') and data.get('sources') and not data.get('citations'):
                    try:
                        cits = compute_citations(str(data['answer']), list(data['sources']))
                        data['citations'] = cits
                    except Exception:
                        pass
                from starlette.responses import JSONResponse
                return JSONResponse(data)
        except Exception:
            return resp
        return resp
