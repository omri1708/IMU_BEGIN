from __future__ import annotations
import json
from fastapi import FastAPI, Request
from typing import Callable
from trustops.opa_eval import OPA


def attach_opa(app: FastAPI) -> None:
    opa = OPA()

    @app.middleware('http')
    async def _opa(request: Request, call_next: Callable):
        role = request.headers.get('X-Role','user')
        user = {'id': request.headers.get('X-User','anon'), 'role': role, 'consent': {}}
        # ABAC on request
        abac = opa.query('policy.abac','allow', {'request': {'user':user, 'action': request.method.lower()}, 'resource': {}})
        if not abac.get('result'):
            from starlette.responses import JSONResponse
            return JSONResponse({'error':'ABAC deny'}, status_code=403)
        resp = await call_next(request)
        try:
            if resp.media_type=='application/json':
                body = b''.join([chunk async for chunk in resp.body_iterator])
                data = json.loads(body.decode('utf-8')) if body else {}
                # Retention/Consent check on resource
                resource = data if isinstance(data, dict) else {}
                keep = opa.query('policy.retention','within', {'resource':resource})
                if not keep.get('result'):
                    from starlette.responses import JSONResponse
                    return JSONResponse({'error':'Retention window exceeded'}, status_code=451)
                from starlette.responses import JSONResponse
                return JSONResponse(data)
        except Exception:
            return resp
        return resp
