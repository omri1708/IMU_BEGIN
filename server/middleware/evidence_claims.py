from __future__ import annotations
from fastapi import FastAPI, Request
from typing import Callable
from grounded.claim_graph import ClaimGraph

MIN_COVER = 0.6  # configurable

def attach_per_claim(app: FastAPI) -> None:
    @app.middleware('http')
    async def _claims(request: Request, call_next: Callable):
        resp = await call_next(request)
        try:
            if resp.media_type == 'application/json':
                body = b''.join([chunk async for chunk in resp.body_iterator])
                import json
                data = json.loads(body.decode('utf-8')) if body else {}
                if isinstance(data, dict) and data.get('answer') and data.get('sources'):
                    cg = ClaimGraph(str(data['answer']), list(data['sources']))
                    data['citations'] = cg.citations
                    data['coverage'] = cg.cover_ratio()
                    data['per_claim'] = cg.per_claim()
                    if data['coverage'] < MIN_COVER:
                        from starlette.responses import JSONResponse
                        return JSONResponse({'error':'CoverageGate','ratio': data['coverage']}, status_code=412)
                from starlette.responses import JSONResponse
                return JSONResponse(data)
        except Exception:
            return resp
        return resp
