from __future__ import annotations
from pathlib import Path
import yaml, json, textwrap
from planner_advanced.asyncapi import gen_asyncapi
from planner_advanced.openapi import gen_openapi

T_APP = '''from fastapi import FastAPI\nfrom server.middleware.otel import instrument_app\nfrom server.middleware.trustops import attach_trustops\nfrom server.middleware.redaction import attach_redaction\nfrom server.middleware.opa_enforcer import attach_opa\napp = FastAPI(title='{name}')\ninstrument_app(app)\nattach_trustops(app)\nattach_redaction(app)\nattach_opa(app)\n@app.get('/healthz')\ndef health(): return {{'ok':True}}\n'''

T_API = '''from fastapi import APIRouter\nrouter = APIRouter(prefix='/api')\n''' # TODO: generated endpoints\n


def generate_microservices(spec_path='.imu_runs/spec.json', base='services/micro'):
    spec = json.loads(Path(spec_path).read_text())
    contexts = spec.get('contexts', [])
    basep = Path(base); basep.mkdir(parents=True, exist_ok=True)
    for ctx in contexts:
        name = ctx['name']
        sp = basep/name; sp.mkdir(parents=True, exist_ok=True)
        (sp/'app.py').write_text(T_APP.format(name=name), encoding='utf-8')
        (sp/'api.py').write_text(T_API, encoding='utf-8')
        asyncapi = gen_asyncapi(name, ctx.get('events_in',[]), ctx.get('events_out',[]))
        openapi = gen_openapi(name, [{'path':'/entities','method':'GET'}])
        (sp/'asyncapi.yaml').write_text(yaml.safe_dump(asyncapi, sort_keys=False, allow_unicode=True), encoding='utf-8')
        (sp/'openapi.yaml').write_text(yaml.safe_dump(openapi, sort_keys=False, allow_unicode=True), encoding='utf-8')
    return len(contexts)

if __name__=='__main__':
    print({'generated': generate_microservices()})
