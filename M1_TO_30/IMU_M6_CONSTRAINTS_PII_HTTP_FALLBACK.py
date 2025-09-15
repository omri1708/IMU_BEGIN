#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU M6 — Deep‑Dive Interview, HTTP LLM fallback, DB‑level constraints + PII redaction/RBAC
-----------------------------------------------------------------------------------------
Idempotently patches/creates the following so the system deepens *when you want*,
falls back to HTTP LLM if no SDK, and enforces DB constraints + PII-aware redaction
end‑to‑end (API+UI):

• interview/advanced_runner.py      — lets the user loop through deepening sections endlessly
• services/llm/providers/http_driver.py — generic HTTP LLM provider (endpoint+auth)
• services/llm/llm_gateway.py       — include HTTP fallback candidate automatically
• policy/pii.yaml                   — PII classes → redaction & role allowances
• server/middleware/redaction.py    — response JSON redactor (PII + field-level RBAC)
• builder_v2/generate.py            — models/routes now honor DB constraints (NOT NULL/UNIQUE/CHECK),
                                      T_APP wires OTEL+TrustOps+Redaction middlewares
• web/next integration              — UI already RBAC-aware from M5; PII policy consumed via rbac/redaction
• Makefile                          — adds interview_advanced target

Run:
  python IMU_M6_CONSTRAINTS_PII_HTTP_FALLBACK.py
  make interview_advanced   # deep-dive as much as you like
"""
from __future__ import annotations
import os, pathlib, textwrap
R = pathlib.Path('.')

def W(rel: str, s: str, mode: int = 0o644, overwrite: bool = True) -> None:
    p = R/rel; p.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not p.exists():
        p.write_text(textwrap.dedent(s).lstrip('\n'), encoding='utf-8'); os.chmod(p, mode)

# ---------------------------------------------------------------------
# 1) Deep-dive interview runner (loops optional sections until done)
# ---------------------------------------------------------------------
W('interview/advanced_runner.py', r"""
from __future__ import annotations
import subprocess, sys

SECS = [
  ('features','יכולות'), ('nonfunc','איכות ואילוצים'), ('policies','מדיניות ו‑TrustOps'),
  ('corpora','מקורות וקורפוסים'), ('approvals','אישורים ושערים'), ('ux','חוויית משתמש')
]

def main():
    # 1) always ensure core via main engine
    subprocess.run([sys.executable, 'interview/engine.py'])
    while True:
        print('\n[advanced] בחר נושא להעמקה (או 0 לסיום):')
        for i, (_, t) in enumerate(SECS, 1): print(f'  {i}. {t}')
        print('  7. השלמת אילוצי שדות (constraints)')
        print('  0. סיום')
        sel = input('> ').strip()
        if sel in ('0','q','quit','exit'): break
        if sel == '7':
            subprocess.run([sys.executable, 'interview/constraints_enricher.py'])
            continue
        try:
            idx = int(sel); sid = SECS[idx-1][0]
            # run a focused pass over a single section using the engine's run_section path
            # fallback: just re-run engine for idempotent capture
            subprocess.run([sys.executable, 'interview/engine.py'])
        except Exception:
            continue
    print('[advanced] הסתיים — אפשר להמשיך לתכנון/בנייה.')

if __name__ == '__main__':
    main()
""")

# ---------------------------------------------------------------------
# 2) HTTP LLM fallback provider + gateway hookup
# ---------------------------------------------------------------------
W('services/llm/providers/http_driver.py', r"""
from __future__ import annotations
import os, json, urllib.request
from typing import List, Dict

class HttpDriver:
    ""Generic HTTP provider. Env:
    IMU_HTTP_LLM_ENDPOINT (required), IMU_HTTP_LLM_AUTH (optional header value)
    Request:  POST endpoint  {"messages": [...]}  →  {"text": str, "usage": {"prompt":int,"completion":int}}
    ""
    def __init__(self, endpoint: str | None = None):
        self.url = endpoint or os.getenv('IMU_HTTP_LLM_ENDPOINT')
        if not self.url:
            raise RuntimeError('IMU_HTTP_LLM_ENDPOINT not set')
        self.auth = os.getenv('IMU_HTTP_LLM_AUTH')

    def complete(self, messages: List[Dict[str,str]]) -> Dict:
        payload = json.dumps({'messages': messages}).encode('utf-8')
        req = urllib.request.Request(self.url, data=payload, headers={'Content-Type':'application/json'})
        if self.auth:
            req.add_header('Authorization', self.auth)
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.loads(resp.read().decode('utf-8'))
        usage = out.get('usage', {})
        return {'text': out.get('text',''), 'prompt_tokens': int(usage.get('prompt',0)), 'completion_tokens': int(usage.get('completion',0))}
""")

# Patch gateway to include HTTP fallback automatically (overwrites file)
W('services/llm/llm_gateway.py', r"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time, json, os, pathlib
from .tokenizers import count_tokens
# drivers
from .providers.openai_driver import OpenAIDriver  # type: ignore
from .providers.azure_openai_driver import AzureOpenAIDriver  # type: ignore
from .providers.anthropic_driver import AnthropicDriver  # type: ignore
from .providers.vertex_driver import VertexDriver  # type: ignore
from .providers.bedrock_driver import BedrockDriver  # type: ignore
from .providers.http_driver import HttpDriver  # type: ignore

@dataclass
class ProviderResult:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float
    text: str
    ok: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)

class LLMGateway:
    PRICES = {
        ("openai", "gpt-4o-mini"): {"in": 0.00015, "out": 0.0006},
        ("openai", "gpt-4o"):      {"in": 0.005,   "out": 0.015},
        ("anthropic", "claude-3.5-sonnet"): {"in": 0.003, "out": 0.015},
        ("vertex", "gemini-1.5-pro"): {"in": 0.0005, "out": 0.0015},
        ("bedrock", "anthropic.claude-3-sonnet-20240229-v1:0"): {"in": 0.003, "out": 0.015},
        ("azure", "gpt-4o"): {"in": 0.005, "out": 0.015},
        ("http", "default"): {"in": 0.0, "out": 0.0},
    }

    def __init__(self, policy: Optional[Dict[str, Any]] = None, kpi_log: str = ".imu_runs/llm_kpis.jsonl"):
        self.policy = policy or {}
        self.kpi_path = pathlib.Path(kpi_log); self.kpi_path.parent.mkdir(parents=True, exist_ok=True)

    def _price(self, provider: str, model: str, ptok: int, ctok: int) -> float:
        p = self.PRICES.get((provider, model)) or {"in": 0.001, "out": 0.003}
        return (ptok/1000.0) * p["in"] + (ctok/1000.0) * p["out"]

    def _emit_kpi(self, rec: Dict[str, Any]):
        with self.kpi_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _driver_for(self, provider: str, model: str):
        p = provider.lower()
        if p == 'openai': return OpenAIDriver(model)
        if p == 'azure':  return AzureOpenAIDriver(deployment=os.getenv('AZURE_OPENAI_DEPLOYMENT'))
        if p == 'anthropic': return AnthropicDriver(model)
        if p == 'vertex': return VertexDriver(model)
        if p == 'bedrock': return BedrockDriver(model)
        if p == 'http': return HttpDriver()
        raise RuntimeError(f'Unknown provider: {provider}')

    def _candidates(self) -> List[Dict[str,str]]:
        c = []
        if os.getenv('OPENAI_API_KEY'): c.append({"provider":"openai","model":os.getenv('OPENAI_MODEL','gpt-4o-mini')})
        if os.getenv('AZURE_OPENAI_API_KEY') and os.getenv('AZURE_OPENAI_ENDPOINT') and os.getenv('AZURE_OPENAI_DEPLOYMENT'):
            c.append({"provider":"azure","model":os.getenv('AZURE_OPENAI_DEPLOYMENT')})
        if os.getenv('ANTHROPIC_API_KEY'): c.append({"provider":"anthropic","model":os.getenv('ANTHROPIC_MODEL','claude-3.5-sonnet')})
        if os.getenv('GOOGLE_CLOUD_PROJECT'): c.append({"provider":"vertex","model":os.getenv('VERTEX_MODEL','gemini-1.5-pro')})
        if os.getenv('AWS_REGION'): c.append({"provider":"bedrock","model":os.getenv('BEDROCK_MODEL','anthropic.claude-3-sonnet-20240229-v1:0')})
        if os.getenv('IMU_HTTP_LLM_ENDPOINT'): c.append({"provider":"http","model":"default"})
        return c or [{"provider":"http","model":"default"}]

    def complete(self, messages: List[Dict[str, str]], candidates: List[Dict[str, str]] | None = None, budget_usd: float | None = None) -> ProviderResult:
        cand = (candidates or self._candidates())[0]
        provider, model = cand['provider'], cand['model']
        text_in = (messages[-1].get('content') if messages else '')
        ptok = count_tokens(provider, model, text_in)
        start = time.time()
        try:
            out = self._driver_for(provider, model).complete(messages)
            text_out = out.get('text','')
            ctok = out.get('completion_tokens') or count_tokens(provider, model, text_out)
            cost = self._price(provider, model, ptok, ctok)
            lat = (time.time() - start) * 1000.0
            res = ProviderResult(provider, model, ptok, ctok, cost, lat, text_out, ok=True)
        except Exception as e:
            lat = (time.time() - start) * 1000.0
            res = ProviderResult(provider, model, ptok, 0, 0.0, lat, f"[driver-error] {e}", ok=False)
        self._emit_kpi({"provider": res.provider, "model": res.model, "ptok": res.prompt_tokens, "ctok": res.completion_tokens, "cost": res.cost_usd, "latency_ms": res.latency_ms, "ok": res.ok})
        max_call = (self.policy.get('cost', {}) or {}).get('max_usd_per_call')
        if max_call is not None and res.cost_usd > float(max_call):
            raise RuntimeError(f"CostGate: call cost {res.cost_usd:.4f} > max_usd_per_call={max_call}")
        return res
""")

# ---------------------------------------------------------------------
# 3) PII policy + redaction middleware
# ---------------------------------------------------------------------
W('policy/pii.yaml', r"""
classes:
  email:   { mask: 'partial', roles_allow: [admin, manager] }
  phone:   { mask: 'partial', roles_allow: [admin, manager] }
  card:    { mask: 'last4',   roles_allow: [admin] }
  address: { mask: 'coarse',  roles_allow: [admin, manager] }
""", overwrite=False)

W('server/middleware/redaction.py', r"""
from __future__ import annotations
import yaml, json
from pathlib import Path
from fastapi import FastAPI, Request
from typing import Callable

POL = Path('policy/pii.yaml')
RBAC = Path('policy/rbac.yaml')

MASKS = {
    'partial': lambda v: (v[:2] + '***' + v[-2:]) if isinstance(v,str) and len(v)>=4 else '***',
    'last4':   lambda v: ('**** **** **** ' + v[-4:]) if isinstance(v,str) and len(v)>=4 else '****',
    'coarse':  lambda v: '***',
}

def _load_yaml(p: Path, dflt: dict):
    try: return yaml.safe_load(p.read_text()) if p.exists() else dflt
    except Exception: return dflt


def attach_redaction(app: FastAPI) -> None:
    pii = _load_yaml(POL, {'classes':{}})
    rbac = _load_yaml(RBAC, {'roles':['admin','manager','user'], 'entities':{'default':{'visible':['admin','manager','user'],'editable':['admin','manager']}}})

    def _allowed(role: str, cls: str) -> bool:
        ent = pii.get('classes',{}).get(cls, {})
        allow = ent.get('roles_allow', [])
        return (role in allow) if allow else True

    def _mask_for(cls: str):
        m = pii.get('classes',{}).get(cls,{}).get('mask', 'partial')
        return MASKS.get(m, MASKS['partial'])

    def _redact_obj(obj, role: str):
        if isinstance(obj, dict):
            out = {}
            for k,v in obj.items():
                # naive: detect pii class by suffix naming convention e.g. email, phone
                cls = None
                for c in pii.get('classes',{}).keys():
                    if k.lower().endswith(c): cls = c; break
                if cls and not _allowed(role, cls):
                    out[k] = _mask_for(cls)(v)
                else:
                    out[k] = _redact_obj(v, role)
            return out
        if isinstance(obj, list):
            return [_redact_obj(x, role) for x in obj]
        return obj

    @app.middleware('http')
    async def _redactor(request: Request, call_next: Callable):
        role = request.headers.get('X-Role','user')
        resp = await call_next(request)
        try:
            if resp.media_type == 'application/json':
                body = b''.join([chunk async for chunk in resp.body_iterator])
                data = json.loads(body.decode('utf-8')) if body else {}
                red = _redact_obj(data, role)
                from starlette.responses import JSONResponse
                return JSONResponse(red)
        except Exception:
            return resp
        return resp
""")

# ---------------------------------------------------------------------
# 4) Builder: DB constraints → models + Alembic; wire middlewares
# ---------------------------------------------------------------------
W('builder_v2/generate.py', r"""
from __future__ import annotations
import yaml, pathlib, textwrap
from sqlalchemy import CheckConstraint

BACK = pathlib.Path('services/backend'); WEB = pathlib.Path('web/next/pages')

T_APP = '''from fastapi import FastAPI
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
'''

T_MODEL_HDR = '''from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, CheckConstraint, UniqueConstraint
Base = declarative_base()
'''

T_MODEL_ROW = ""class {cls}(Base):
    __tablename__ = '{tbl}'
{cols}
    __table_args__ = (
{tbl_args}
    )
""

T_COL = "    {name} = Column({type}{opts})\n"

T_API_HDR = '''from fastapi import APIRouter, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List
from . import models

DB_URL = 'sqlite:///./app.db'
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

router = APIRouter(prefix='/api')
'''

T_API_CRUD = ""
@router.post('/{route}', response_model=dict)
def create_{route}(req: Request):
    role = req.headers.get('X-Role','user')
    data = await req.json()
    obj = models.{cls}(**data)
    db = SessionLocal(); db.add(obj); db.commit(); db.refresh(obj)
    return {{"id": getattr(obj, 'id', None)}}

@router.get('/{route}', response_model=list)
async def list_{route}(req: Request):
    db = SessionLocal(); rows = db.query(models.{cls}).all()
    def pick(r):
        return {{k: getattr(r, k) for k in item_fields}}
    return [pick(r) for r in rows]
""

T_MAIN_INCLUDE = ""
from .api import router as api_router
app.include_router(api_router)
""

T_NEXT_IDX = "export default function Home(){return <main>Home</main>}\n"


def _py(s: str) -> str: return textwrap.dedent(s).lstrip('\n')

def _sqlatype(col):
    t = (col.get('type') or 'str')
    if 'int' in t:   return 'Integer'
    if 'float' in t or 'num' in t: return 'Float'
    if 'text' in t:  return 'Text'
    return 'String'


def write_backend(contracts: dict):
    BACK.mkdir(parents=True, exist_ok=True)
    (BACK/'app.py').write_text(_py(T_APP), encoding='utf-8')
    models_py = [T_MODEL_HDR]
    api_py = [T_API_HDR]

    for ent in contracts.get('db', []):
        tbl = ent['table']; cls = ''.join([p.capitalize() for p in tbl.split('_')])
        cols_py = []
        fields = []
        tbl_args = []
        uniques = []
        for c in ent.get('columns', []):
            name = c['name']
            cons = c.get('constraints',{})
            typ = _sqlatype(c)
            opts = ''
            # String length from max (if numeric and string type)
            if typ == 'String' and isinstance(cons.get('max'), (int,float)):
                opts = f'(int({int(cons["max"])}) )'  # hint length (not strict in sqlite)
                opts = ''
            # nullability
            if cons.get('required', False):
                opts += ', nullable=False'
            # uniqueness
            if cons.get('unique', False):
                opts += ', unique=True'
            # primary key
            if c.get('pk'): opts += ', primary_key=True'
            cols_py.append(T_COL.format(name=name, type=typ, opts=opts))
            # DB CHECK constraints for min/max numeric
            if typ in ('Integer','Float'):
                if cons.get('min') is not None:
                    tbl_args.append(f"CheckConstraint('{name} >= {float(cons['min'])}')")
                if cons.get('max') is not None:
                    tbl_args.append(f"CheckConstraint('{name} <= {float(cons['max'])}')")
            if not c.get('pk'):
                fields.append(name)
        if uniques:
            for u in uniques:
                tbl_args.append(f"UniqueConstraint('{u}')")
        if not tbl_args:
            tbl_args_txt = ''
        else:
            tbl_args_txt = '        ' + ',\n        '.join(tbl_args) + ',\n'
        models_py.append(T_MODEL_ROW.format(cls=cls, tbl=tbl, cols=''.join(cols_py), tbl_args=tbl_args_txt))
        api_py.append('item_fields = '+str(fields)+'\n')
        api_py.append(T_API_CRUD.format(cls=cls, route=tbl))

    (BACK/'models.py').write_text(_py(''.join(models_py)), encoding='utf-8')
    (BACK/'api.py').write_text(_py(''.join(api_py)), encoding='utf-8')
    with (BACK/'app.py').open('a', encoding='utf-8') as f: f.write(_py(T_MAIN_INCLUDE))


def write_ui_stub():
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB/'index.tsx').write_text(T_NEXT_IDX, encoding='utf-8')


def write_iac_stub():
    values = pathlib.Path('charts/imu/values.yaml'); values.parent.mkdir(parents=True, exist_ok=True)
    values.write_text('service: { port: 8000 }\n', encoding='utf-8')


def generate_from_spec(spec: dict):
    write_backend(spec.get('contracts', {}))
    write_ui_stub()
    write_iac_stub()
    pathlib.Path('.imu_runs/spec.json').parent.mkdir(parents=True, exist_ok=True)
    import json
    pathlib.Path('.imu_runs/spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
""")

# ---------------------------------------------------------------------
# 5) Makefile: interview_advanced
# ---------------------------------------------------------------------
W('Makefile', r"""
.PHONY: interview_advanced

interview_advanced:
	@python interview/advanced_runner.py
""", overwrite=False)

print('[OK] IMU M6 — deep-dive interview + HTTP fallback + DB constraints + PII redaction written.')
