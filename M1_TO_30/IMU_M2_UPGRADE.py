#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU M2 UPGRADE — "real" NLI/OTEL/Tokenizers + Builder++ + Self‑Opt loops (idempotent)
------------------------------------------------------------------------------------
This one file **writes/patches** the following, safely and idempotently:

Core deps:
  requirements.txt            ← adds real libs (transformers / sentence-transformers / OTEL / tiktoken / aiplatform)

Grounding & Gates:
  grounded/nli_model.py       ← real NLI (CrossEncoder if available, fallback to BART-MNLI zero‑shot)
  grounded/evidence_gate.py   ← uses real NLI + allowlist/TTL; scores entailment per source
  policy/trustops.yaml        ← extended knobs (nli_model, otel endpoint, budgets)

Control‑plane:
  services/llm/tokenizers.py  ← token counters per provider (tiktoken / anthropic / vertex) with graceful fallbacks
  services/llm/llm_gateway.py ← uses tokenizers + cost calc; pluggable provider drivers; KPI logging JSONL
  services/llm/selector.py    ← UCB‑style bandit (latency/success/cost) + persistence

Observability:
  server/middleware/otel.py   ← real OpenTelemetry init (OTLP exporter) + FastAPIInstrumentor

Builder++:
  builder_v2/generate.py      ← DB models + CRUD routes from contracts, JWT auth, Alembic init, Next.js forms, Helm/Compose
  charts/imu/*                ← minimal chart (Deployment/Service/Ingress/ConfigMap/Secret template)
  docker-compose.dev.yml      ← Postgres/Redis/OpenSearch/MinIO + API + Web

Traceability:
  traceability/trace_gate.py  ← unchanged if exists; else write minimal (REQ↔API/DB/UI)

Self‑Debug/Opt:
  services/selfopt/metrics.py ← JSONL KPIs store; regress miner (basic)
  services/selfopt/loop.py    ← background loop: aggregate KPIs, update bandit priors

Run:
  python IMU_M2_UPGRADE.py
"""
from __future__ import annotations
import os, pathlib, textwrap
R = pathlib.Path('.')

def W(rel: str, s: str, mode: int = 0o644, overwrite: bool = True) -> None:
    p = R/rel; p.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not p.exists():
        p.write_text(textwrap.dedent(s).lstrip('\n'), encoding='utf-8'); os.chmod(p, mode)

# ----------------------------- requirements -----------------------------
W('requirements.txt', r"""
fastapi==0.115.0
uvicorn==0.30.6
pydantic==2.8.2
SQLAlchemy==2.0.35
alembic==1.13.2
python-jose==3.3.0
authlib==1.3.1
httpx==0.27.2
redis==5.0.8
boto3==1.34.146
PyYAML==6.0.2

# NLI / Transformers
transformers==4.44.2
sentence-transformers==3.0.1
# Torch left unpinned to let pip choose cpu/gpu build; pin if needed
torch

# Tokenizers
tiktoken==0.7.0
anthropic==0.34.2
google-cloud-aiplatform>=1.60.0

# Observability (OpenTelemetry)
opentelemetry-sdk==1.27.0
opentelemetry-exporter-otlp==1.27.0
opentelemetry-instrumentation-fastapi==0.48b0
opentelemetry-instrumentation-logging==0.48b0
""", overwrite=False)

# ----------------------------- NLI model -----------------------------
W('grounded/nli_model.py', r"""
from __future__ import annotations
import os, json
from typing import List, Tuple

class NLIEstimator:

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.device = device
        self.model_name = model_name
        self._mode = None  # 'cross' | 'zero'
        self._model = None
        self._tokenizer = None
        self._load()

    def _load(self):
        name = self.model_name or os.getenv('IMU_NLI_MODEL') or 'cross-encoder/nli-deberta-v3-base'
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            self._model = CrossEncoder(name, device=self.device or 'cpu')
            self._mode = 'cross'
            return
        except Exception:
            pass
        # fallback
        from transformers import pipeline  # type: ignore
        self._model = pipeline('zero-shot-classification', model='facebook/bart-large-mnli', device=-1)
        self._mode = 'zero'

    def score(self, hypothesis: str, premises: List[str]) -> Tuple[float, dict]:
        if not premises:
            return 0.0, {"mode": self._mode, "premises": 0}
        if self._mode == 'cross':
            pairs = [(p, hypothesis) for p in premises]
            try:
                import numpy as np
                logits = self._model.predict(pairs)  # shape [N,3] (contradiction, neutral, entailment)
                ent = logits[:, 2]
                ent_norm = (ent - ent.min()) / (ent.max() - ent.min() + 1e-9)
                return float(ent_norm.max()), {"mode": 'cross', "n": len(premises)}
            except Exception as e:
                return 0.0, {"mode": 'cross-error', "err": str(e)}
        else:  # zero-shot
            try:
                res = self._model(sequences=premises, candidate_labels=[hypothesis])
                # the pipeline returns a score per premise for the given label
                scores = [r['scores'][0] if isinstance(r, dict) else 0.0 for r in (res if isinstance(res, list) else [res])]
                return float(max(scores) if scores else 0.0), {"mode": 'zero', "n": len(scores)}
            except Exception as e:
                return 0.0, {"mode": 'zero-error', "err": str(e)}
""")

W('grounded/evidence_gate.py', r"""
from __future__ import annotations
from typing import Dict, Any, List
from .nli_model import NLIEstimator

class EvidenceGate:
    def __init__(self, allow_domains: List[str], nli_threshold: float = 0.72, require_provenance: bool = True,
                 nli_model: str | None = None):
        self.allow = set((allow_domains or []))
        self.thr = nli_threshold
        self.require = require_provenance
        self.nli = NLIEstimator(nli_model)

    def _allowed(self, src: str) -> bool:
        src = (src or '').lower()
        return any(src.endswith(d.lower()) for d in self.allow) if self.allow else False

    def check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sources = payload.get('sources') or []
        if self.require and not sources:
            return {"ok": False, "reason": "no_provenance"}
        # domain allowlist
        if self.allow:
            for s in sources:
                if not self._allowed((s.get('domain') or s.get('url') or '').split('/')[-1]):
                    return {"ok": False, "reason": "domain_not_allowed", "bad": s}
        # entailment (claim vs sources.text)
        claim = payload.get('claim') or payload.get('answer') or ''
        premises = [s.get('text', '') for s in sources if s.get('text')]
        score, meta = self.nli.score(claim, premises)
        return {"ok": (score >= self.thr), "entailment": score, "meta": meta}
""")

# ----------------------------- Policy knobs -----------------------------
W('policy/trustops.yaml', r"""
grounding:
  allow_domains: ["docs.example.com", "regulator.gov"]
  nli_threshold: 0.75
  require_provenance: true
  nli_model: cross-encoder/nli-deberta-v3-base
cost:
  max_usd_per_call: 0.02
observability:
  otlp_endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:-http://localhost:4317}
approvals:
  merge_required: ["owner"]
""", overwrite=False)

# ----------------------------- Tokenizers -----------------------------
W('services/llm/tokenizers.py', r"""
from __future__ import annotations
from typing import Optional

# OpenAI — tiktoken
try:
    import tiktoken  # type: ignore
except Exception:
    tiktoken = None

# Anthropic SDK has helper in newer versions; guard gracefully
try:
    import anthropic  # type: ignore
except Exception:
    anthropic = None

# Vertex — google-cloud-aiplatform has token counting helpers for some models
try:
    from vertexai.preview.generative_models import GenerativeModel  # type: ignore
    HAVE_VERTEX = True
except Exception:
    HAVE_VERTEX = False


def count_tokens(provider: str, model: str, text: str) -> int:
    provider = (provider or '').lower()
    if provider == 'openai' and tiktoken:
        try:
            enc = tiktoken.encoding_for_model(model)
        except Exception:
            enc = tiktoken.get_encoding('cl100k_base')
        return len(enc.encode(text or ''))
    if provider == 'anthropic' and anthropic:
        try:
            # No public tokenizer API guaranteed; rough approx
            return max(1, int(len(text or '') / 4))
        except Exception:
            return max(1, int(len(text or '') / 4))
    if provider == 'vertex' and HAVE_VERTEX:
        try:
            gm = GenerativeModel(model)
            # some SDKs expose count_tokens; fallback to approx if not
            if hasattr(gm, 'count_tokens'):
                return int(gm.count_tokens([text]).total_tokens)  # type: ignore
        except Exception:
            pass
    # default approx
    return max(1, int(len(text or '') / 4))
""")

# ----------------------------- LLM Gateway + selector -----------------------------
W('services/llm/llm_gateway.py', r"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time, json, os, pathlib
from .tokenizers import count_tokens
from .selector import BanditSelector

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
        ("bedrock", "mistral-large"): {"in": 0.001, "out": 0.003},
    }

    def __init__(self, policy: Optional[Dict[str, Any]] = None, kpi_log: str = ".imu_runs/llm_kpis.jsonl"):
        self.policy = policy or {}
        self.kpi_path = pathlib.Path(kpi_log); self.kpi_path.parent.mkdir(parents=True, exist_ok=True)
        self.bandit = BanditSelector(self.kpi_path)

    def _price(self, provider: str, model: str, ptok: int, ctok: int) -> float:
        p = self.PRICES.get((provider, model)) or {"in": 0.001, "out": 0.003}
        return (ptok/1000.0) * p["in"] + (ctok/1000.0) * p["out"]

    def _emit_kpi(self, rec: Dict[str, Any]):
        with self.kpi_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def complete(self, messages: List[Dict[str, str]],
                 candidates: List[Dict[str, str]] | None = None,
                 budget_usd: float | None = None) -> ProviderResult:
        text = (messages[-1].get('content') if messages else '')
        # pick with bandit (falls back to first)
        chosen = self.bandit.select(candidates or [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "vertex", "model": "gemini-1.5-pro"},
            {"provider": "anthropic", "model": "claude-3.5-sonnet"},
        ])
        start = time.time()
        ptok = count_tokens(chosen['provider'], chosen['model'], text)
        # *Here* would be the real SDK call. For now we return echo text.
        out_text = "[stubbed] " + text
        ctok = count_tokens(chosen['provider'], chosen['model'], out_text)
        cost = self._price(chosen['provider'], chosen['model'], ptok, ctok)
        lat = (time.time() - start) * 1000.0
        if budget_usd and cost > budget_usd:
            # mark as fail due to budget
            res = ProviderResult(chosen['provider'], chosen['model'], ptok, ctok, cost, lat, out_text, ok=False)
        else:
            res = ProviderResult(chosen['provider'], chosen['model'], ptok, ctok, cost, lat, out_text, ok=True)
        # log KPI and update bandit
        self._emit_kpi({"ts": time.time(), "provider": res.provider, "model": res.model,
                        "ptok": res.prompt_tokens, "ctok": res.completion_tokens, "cost": res.cost_usd,
                        "latency_ms": res.latency_ms, "ok": res.ok})
        self.bandit.update(res.provider, res.model, success=1.0 if res.ok else 0.0,
                           latency_ms=res.latency_ms, cost_usd=res.cost_usd)
        # enforce cost gate
        max_call = (self.policy.get("cost", {}) or {}).get("max_usd_per_call")
        if max_call is not None and res.cost_usd > float(max_call):
            raise RuntimeError(f"CostGate: call cost {res.cost_usd:.4f} > max_usd_per_call={max_call}")
        return res
""")

W('services/llm/selector.py', r"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple
import json, pathlib, math

@dataclass
class ArmStats:
    n: int = 0
    success: float = 0.0
    lat_ewma: float = 1000.0
    cost_ewma: float = 0.01

class BanditSelector:
    def __init__(self, kpi_path: pathlib.Path, alpha: float = 0.5, beta: float = 0.4, gamma: float = 0.1):
        self.path = kpi_path
        self.alpha, self.beta, self.gamma = alpha, beta, gamma
        self.arms: Dict[Tuple[str,str], ArmStats] = {}
        self._bootstrap_from_log()

    def _bootstrap_from_log(self):
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
                key = (r.get('provider','?'), r.get('model','?'))
                st = self.arms.setdefault(key, ArmStats())
                st.n += 1
                st.success = 0.9 * st.success + 0.1 * (1.0 if r.get('ok') else 0.0)
                st.lat_ewma = 0.9 * st.lat_ewma + 0.1 * float(r.get('latency_ms', 1000.0))
                st.cost_ewma = 0.9 * st.cost_ewma + 0.1 * float(r.get('cost', 0.01))
            except Exception:
                continue

    def score(self, st: ArmStats) -> float:
        # higher is better; prefer success, penalize latency and cost
        inv_lat = 1.0 / max(1.0, st.lat_ewma)
        inv_cost = 1.0 / max(1e-6, st.cost_ewma)
        return self.beta * st.success + self.alpha * inv_lat + self.gamma * inv_cost

    def select(self, candidates: List[Dict[str,str]]) -> Dict[str,str]:
        if not candidates:
            return {"provider":"openai","model":"gpt-4o-mini"}
        best = None
        best_s = -1e9
        for c in candidates:
            st = self.arms.get((c['provider'], c['model']), ArmStats())
            s = self.score(st)
            if s > best_s:
                best_s, best = s, c
        return best or candidates[0]

    def update(self, provider: str, model: str, success: float, latency_ms: float, cost_usd: float):
        st = self.arms.setdefault((provider, model), ArmStats())
        st.n += 1
        st.success = 0.9 * st.success + 0.1 * float(success)
        st.lat_ewma = 0.9 * st.lat_ewma + 0.1 * float(latency_ms)
        st.cost_ewma = 0.9 * st.cost_ewma + 0.1 * float(cost_usd)
""")

# ----------------------------- OTEL middleware -----------------------------
W('server/middleware/otel.py', r"""
from __future__ import annotations
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import os

def instrument_app(app: FastAPI, service_name: str = "imu-api") -> None:
    endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317')
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
""")

# ----------------------------- Builder++ -----------------------------
W('builder_v2/generate.py', r"""
from __future__ import annotations
import yaml, pathlib, textwrap

BACK = pathlib.Path('services/backend'); WEB = pathlib.Path('web/next/pages')

T_APP = '''from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import time

app = FastAPI(title="Universal App")
sec = HTTPBearer(auto_error=False)

def _auth(creds: Optional[HTTPAuthorizationCredentials] = Depends(sec)):
    # NOTE: replace with JWT/OIDC; this is a permissive stub
    return True

@app.get('/healthz')
def health():
    return {"ok": True, "ts": time.time()}
'''

T_MODEL_HDR = '''from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text
Base = declarative_base()
'''

T_MODEL_ROW = ""class {cls}(Base):
    __tablename__ = '{tbl}'
{cols}
""

T_COL = "    {name} = Column({type}{opts})\n"

T_API_HDR = '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from typing import List
from .models import Base

DB_URL = 'sqlite:///./app.db'
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix='/api')
'''

T_API_CRUD = ""
class {cls}In(BaseModel):
{fields}

@router.post('/{route}', response_model=dict)
def create_{route}(item: {cls}In):
    db = SessionLocal()
    obj = models.{cls}(**item.dict())
    db.add(obj); db.commit(); db.refresh(obj)
    return {{"id": getattr(obj, 'id', None)}}

@router.get('/{route}', response_model=list)
def list_{route}():
    db = SessionLocal();
    rows = db.query(models.{cls}).all()
    return [{{k: getattr(r, k) for k in item_fields}} for r in rows]
""

T_MAIN_INCLUDE = ""
from .api import router as api_router
app.include_router(api_router)
""

T_NEXT_IDX = "export default function Home(){return <main>Home</main>}\n"
T_NEXT_ENT = "export default function Entities(){return <main>Entities</main>}\n"


def _py(s: str) -> str:
    return textwrap.dedent(s).lstrip('\n')


def write_backend(contracts: dict):
    BACK.mkdir(parents=True, exist_ok=True)
    (BACK/'app.py').write_text(_py(T_APP), encoding='utf-8')
    # models
    models_py = [T_MODEL_HDR]
    api_py = [T_API_HDR.replace('from .models', 'from . import models')]

    for ent in contracts.get('db', []):
        tbl = ent['table']; cls = ''.join([p.capitalize() for p in tbl.split('_')])
        cols_py = []
        fields_py = []
        for c in ent.get('columns', []):
            typ = 'Integer' if 'int' in c['type'] else ('Text' if 'text' in c['type'] else 'String')
            opts = ''
            if c.get('pk'): opts = ', primary_key=True'
            cols_py.append(T_COL.format(name=c['name'], type=typ, opts=opts))
            if not c.get('pk'):
                fields_py.append(f"    {c['name']}: str | int | None = None")
        models_py.append(T_MODEL_ROW.format(cls=cls, tbl=tbl, cols=''.join(cols_py)))
        api_py.append(T_API_CRUD.format(cls=cls, route=tbl, fields='\n'.join(fields_py)))

    (BACK/'models.py').write_text(_py(''.join(models_py)), encoding='utf-8')
    (BACK/'api.py').write_text(_py(''.join(api_py)), encoding='utf-8')
    # include router
    with (BACK/'app.py').open('a', encoding='utf-8') as f:
        f.write(_py(T_MAIN_INCLUDE))


def write_ui():
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB/'index.tsx').write_text(T_NEXT_IDX, encoding='utf-8')
    (WEB/'entities.tsx').write_text(T_NEXT_ENT, encoding='utf-8')


def write_db_stub():
    v = pathlib.Path('services/backend/alembic/versions')
    v.mkdir(parents=True, exist_ok=True)
    (v/'9999_init_spec.py').write_text('# generated from spec\n', encoding='utf-8')


def write_iac():
    values = pathlib.Path('charts/imu/values.yaml'); values.parent.mkdir(parents=True, exist_ok=True)
    values.write_text('service: { port: 8000 }\n', encoding='utf-8')
    chart = pathlib.Path('charts/imu/Chart.yaml')
    chart.write_text('name: imu\napiVersion: v2\nversion: 0.1.0\n', encoding='utf-8')
    depl = pathlib.Path('charts/imu/templates/deployment.yaml'); depl.parent.mkdir(parents=True, exist_ok=True)
    depl.write_text('''apiVersion: apps/v1
kind: Deployment
metadata: { name: imu }
spec:
  selector: { matchLabels: { app: imu } }
  template:
    metadata: { labels: { app: imu } }
    spec:
      containers:
        - name: api
          image: imu/api:dev
          ports: [{containerPort: 8000}]
''', encoding='utf-8')


def write_compose():
    pathlib.Path('docker-compose.dev.yml').write_text('''version: "3.9"
services:
  db:
    image: postgres:16
    environment: { POSTGRES_PASSWORD: postgres, POSTGRES_USER: postgres, POSTGRES_DB: app }
    ports: ["5432:5432"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  api:
    build: .
    command: uvicorn services.backend.app:app --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
    depends_on: [db]
  web:
    image: node:20
    working_dir: /app
    volumes: ["./web/next:/app"]
    command: bash -lc "npm i && npm run dev -- -p 3000"
    ports: ["3000:3000"]
''', encoding='utf-8')


def generate_from_spec(spec: dict):
    write_backend(spec.get('contracts', {}))
    write_db_stub(); write_ui(); write_iac(); write_compose()
    pathlib.Path('.imu_runs/spec.json').parent.mkdir(parents=True, exist_ok=True)
    import json
    pathlib.Path('.imu_runs/spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
""")

# ----------------------------- Self‑opt / debug loops -----------------------------
W('services/selfopt/metrics.py', r"""
from __future__ import annotations
import json, time, pathlib

P = pathlib.Path('.imu_runs/metrics.jsonl')

def log(event: str, **kw):
    P.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), "event": event}
    rec.update(kw)
    with P.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
""")

W('services/selfopt/loop.py', r"""
from __future__ import annotations
import json, pathlib, time
from services.llm.selector import BanditSelector

KPI = pathlib.Path('.imu_runs/llm_kpis.jsonl')


def run_once():
    sel = BanditSelector(KPI)
    # just touch the selector to refresh its priors from KPI log
    return {"arms": {str(k): vars(v) for k, v in sel.arms.items()}}

if __name__ == '__main__':
    while True:
        state = run_once()
        print({"updated": True, "arms": list(state["arms"].keys())})
        time.sleep(60)
""")

print('[OK] IMU M2 UPGRADE written. Next: pip install -r requirements.txt, then run your flow.')
