from __future__ import annotations
import json
from fastapi import FastAPI, Request
from typing import Callable
from .redaction_core import load_policies, apply_redaction


def attach_redaction(app: FastAPI) -> None:
    pii, rbac = load_policies()

    @app.middleware('http')
    async def _redactor(request: Request, call_next: Callable):
        role = request.headers.get('X-Role','user')
        resp = await call_next(request)
        try:
            if resp.media_type == 'application/json':
                body = b''.join([chunk async for chunk in resp.body_iterator])
                data = json.loads(body.decode('utf-8')) if body else {}
                red = apply_redaction(data, role, pii, rbac)
                from starlette.responses import JSONResponse
                return JSONResponse(red)
        except Exception:
            return resp
        return resp
