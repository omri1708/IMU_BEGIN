#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU M1 FIXPACK — close the core gaps now (idempotent)
-----------------------------------------------------
This script patches/creates the minimal missing backbone so your
“Interview + Orchestrator V2” becomes runnable with traceability,
policy gates, a unifying LLM gateway (multi‑provider ready), and
seeded planning from interview outputs.

It is SAFE and IDEMPOTENT: re-running overwrites only the files it owns.

What it adds/updates:
  ✓ interview/adapter.py                  — adapter from interview outputs → planner seeds
  ✓ planner_v2/pipeline.py               — accepts seeds (contracts/arch/policy/corpora/ui)
  ✓ services/llm/llm_gateway.py          — multi‑provider abstraction + cost/KPI stubs
  ✓ traceability/trace_gate.py           — REQ↔(API/DB/UI) coverage gate (CI‑ready)
  ✓ server/middleware/otel.py            — stub instrumentation hook
  ✓ server/middleware/trustops.py        — Evidence/Cost/Allowlist enforcement stub
  ✓ grounded/evidence_gate.py            — programmable Evidence gate (NLI stub)
  ✓ gen_universal.py (update)            — “use interview seeds if exist” flow
  ✓ policy/trustops.yaml (if missing)    — default strict policy
  ✓ corpora/allowlist.yaml (if missing)  — allowlist skeleton
  ✓ Makefile (targets)                   — interview / trace / plan / build / run
  ✓ README_M1.md                         — quick usage

Usage:
  python IMU_M1_FIXPACK.py
"""

from __future__ import annotations
import os, pathlib, textwrap, json, re
R = pathlib.Path(".").resolve()

def W(rel: str, s: str, mode: int = 0o644, overwrite: bool = True) -> None:
    p = R/rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not p.exists():
        p.write_text(textwrap.dedent(s).lstrip("\n"), encoding="utf-8")
        os.chmod(p, mode)

# ------------------------------------------------------------
# 1) Interview adapter → planner seeds
# ------------------------------------------------------------
W("interview/adapter.py", r"""
from pathlib import Path
import json, yaml

def load_from_interview():
    req_p = Path("specs/requirements.yaml")
    arch_p = Path("specs/arch.yaml")
    api_p = Path("specs/contracts/api.yaml")
    db_p  = Path("specs/contracts/db.yaml")
    ui_p  = Path("specs/contracts/ui.yaml")

    if not (req_p.exists() and arch_p.exists() and api_p.exists() and db_p.exists() and ui_p.exists()):
        raise FileNotFoundError("Missing interview outputs under specs/*")

    req = yaml.safe_load(req_p.read_text())
    arch = yaml.safe_load(arch_p.read_text())
    contracts = {
        "api": yaml.safe_load(api_p.read_text())["api"],
        "db":  yaml.safe_load(db_p.read_text())["db"],
        "ui":  yaml.safe_load(ui_p.read_text())["ui"],
    }
    policy   = yaml.safe_load(Path("policy/trustops.yaml").read_text()) if Path("policy/trustops.yaml").exists() else {}
    corpora  = yaml.safe_load(Path("corpora/allowlist.yaml").read_text()) if Path("corpora/allowlist.yaml").exists() else {}
    profile  = json.loads(Path("ui/presentation_profile.json").read_text()) if Path("ui/presentation_profile.json").exists() else {}

    nl = "; ".join(r["title"] for r in req.get("requirements", [])) or "High-level goal"
    state = json.loads(Path(".imu_runs/state.json").read_text()) if Path(".imu_runs/state.json").exists() else {"answers":{}}
    personas = state["answers"].get("personas", [])
    flows    = state["answers"].get("flows", [])

    seeds = {"contracts": contracts, "arch": arch, "policy": policy, "corpora": corpora, "ui": profile}
    arch_pref = arch.get("architecture") or arch.get("style")
    return nl, personas, flows, arch_pref, seeds
""")

# ------------------------------------------------------------
# 2) Planner v2 pipeline — accept & merge seeds
# ------------------------------------------------------------
W("planner_v2/pipeline.py", r"""
from __future__ import annotations
from typing import Dict, Any, List
from .domain_induction import induce_domains


def intent_decompose(nl: str) -> Dict[str, Any]:
    lines = [l.strip() for l in nl.replace("\n", ".").split('.') if l.strip()]
    return {"explicit": lines[:3], "implicit": lines[3:6]}


def ux_ia(personas: List[str], flows: List[str]) -> Dict[str, Any]:
    screens = ["Home", "Dashboard", "Search", "Admin"] + [str(f).title() for f in (flows or [])[:3]]
    return {"sitemap": screens, "nav": ["Home", "Search", "Admin"]}


def bounded_contexts(domains: List[str], intents: Dict[str, Any]) -> List[Dict[str, Any]]:
    ctx = []
    for d in domains:
        ctx.append({"name": f"{d}_core", "capabilities": intents["explicit"][:2]})
        ctx.append({"name": f"{d}_ops",  "capabilities": intents["implicit"][:2]})
    return ctx


def arch_synthesis(style: str | None, ctxs: List[Dict[str, Any]]) -> Dict[str, Any]:
    style = style or ("microservices" if len(ctxs) > 3 else "monolith")
    return {"style": style, "services": ([c["name"] for c in ctxs] if style != "monolith" else ["app"]),
            "events": ["entity.created", "entity.updated"]}


def constraint_solve(slo: Dict[str, Any], nonfunc: Dict[str, Any]) -> Dict[str, Any]:
    def parse_num(s: str, dflt: int):
        import re
        m = re.search(r"(\d+)", str(s) or "")
        return int(m.group(1)) if m else dflt
    def parse_float(s: str, dflt: float):
        import re
        m = re.search(r"(0\.\d+|1\.0)", str(s) or "")
        return float(m.group(1)) if m else dflt
    return {"p95_latency_ms": parse_num(slo.get("p95_latency_ms", "<=800"), 800),
            "ok_rate": parse_float(nonfunc.get("ok_rate", ">=0.99"), 0.99)}


def compile_spec(nl: str, personas: List[str], flows: List[str],
                 arch_pref: str | None = None, seeds: Dict[str, Any] | None = None) -> Dict[str, Any]:
    intents = intent_decompose(nl)
    domains = induce_domains(nl)
    ia = ux_ia(personas, flows)
    ctxs = bounded_contexts(domains, intents)
    arch = arch_synthesis(arch_pref, ctxs)
    constraints = constraint_solve({"p95_latency_ms": "<=800"}, {"ok_rate": ">=0.99"})

    # default contracts
    apis = [{"id": "API-001", "path": "/entities", "method": "POST", "req": ["REQ-001"]},
            {"id": "API-002", "path": "/entities", "method": "GET",  "req": ["REQ-001"]}]
    db   = [{"id": "DB-001", "table": "entities", "req": ["REQ-001"],
             "columns": [{"name": "id", "type": "int", "pk": True}, {"name": "name", "type": "str"}, {"name": "description", "type": "text"}]}]
    ui   = [{"id": "UI-001", "screen": "Entities", "route": "/entities", "req": ["REQ-001"]}]

    if seeds and "contracts" in seeds:
        c = seeds["contracts"]
        apis = c.get("api", apis); db = c.get("db", db); ui = c.get("ui", ui)
    if seeds and "arch" in seeds and isinstance(seeds["arch"], dict):
        arch["style"] = seeds["arch"].get("architecture", arch.get("style"))

    spec = {
        "requirements": {"explicit": intents["explicit"], "implicit": intents["implicit"]},
        "domains": domains, "ux": ia, "contexts": ctxs, "arch": arch, "constraints": constraints,
        "contracts": {"api": apis, "db": db, "ui": ui},
        "policy": (seeds or {}).get("policy", {}),
        "corpora": (seeds or {}).get("corpora", {}),
        "ui_profile": (seeds or {}).get("ui", {}),
    }
    return spec
""")

# ------------------------------------------------------------
# 3) LLM Gateway — multi‑provider abstraction + cost/KPI stubs
# ------------------------------------------------------------
W("services/llm/llm_gateway.py", r"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time, os

@dataclass
class ProviderResult:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)


class LLMGateway:
    ""
    Unifying shim over multiple providers.  NOTE: This is a stubbed gateway: it *accounts* and *routes*, but does not call real SDKs here.
    Drop-in calls can be added where allowed.
    ""
    PRICES = {
        # rough defaults (USD / 1K tokens). Replace with real tables per account.
        ("openai", "gpt-4o-mini"): {"in": 0.00015, "out": 0.0006},
        ("openai", "gpt-4o"):      {"in": 0.005,   "out": 0.015},
        ("anthropic", "claude-3.5-sonnet"): {"in": 0.003, "out": 0.015},
        ("azure", "gpt-4o"): {"in": 0.005, "out": 0.015},
        ("vertex", "gemini-1.5-pro"): {"in": 0.0005, "out": 0.0015},
        ("bedrock", "mistral-large"): {"in": 0.001, "out": 0.003},
    }

    def __init__(self, policy: Optional[Dict[str, Any]] = None):
        self.policy = policy or {}
        self.kpis: List[ProviderResult] = []

    def _approx_tokens(self, text: str) -> int:
        # ultra simple token approx — replace with real tokenizers where available
        return max(1, int(len(text) / 4))

    def _price(self, provider: str, model: str, ptok: int, ctok: int) -> float:
        p = self.PRICES.get((provider, model)) or {"in": 0.001, "out": 0.003}
        return (ptok/1000.0) * p["in"] + (ctok/1000.0) * p["out"]

    def complete(self, messages: List[Dict[str, str]],
                 candidates: List[Dict[str, str]] | None = None,
                 budget_usd: float | None = None) -> ProviderResult:
        start = time.time()
        text = (messages[-1].get("content") if messages else "")
        ptok = self._approx_tokens(text)
        # choose provider/model: naive example honoring budget preference
        preferred = candidates or [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "vertex", "model": "gemini-1.5-pro"},
            {"provider": "anthropic", "model": "claude-3.5-sonnet"},
        ]
        chosen = preferred[0]
        est_cost = self._price(chosen["provider"], chosen["model"], ptok, 200)
        if budget_usd and est_cost > budget_usd and len(preferred) > 1:
            chosen = preferred[1]
            est_cost = self._price(chosen["provider"], chosen["model"], ptok, 200)
        # fake completion
        out_text = "[stubbed] " + text
        ctok = self._approx_tokens(out_text)
        cost = self._price(chosen["provider"], chosen["model"], ptok, ctok)
        latency = (time.time() - start) * 1000.0
        res = ProviderResult(chosen["provider"], chosen["model"], ptok, ctok, cost, latency, out_text)
        self.kpis.append(res)
        # budget enforcement
        max_call = (self.policy.get("cost", {}) or {}).get("max_usd_per_call")
        if max_call is not None and cost > float(max_call):
            raise RuntimeError(f"CostGate: call cost {cost:.4f} exceeds max_usd_per_call={max_call}")
        return res
""")

# ------------------------------------------------------------
# 4) Traceability Gate — REQ ↔ artifacts coverage
# ------------------------------------------------------------
W("traceability/trace_gate.py", r"""
from pathlib import Path
import json, yaml, sys

req = yaml.safe_load(Path("specs/requirements.yaml").read_text())['requirements']
api = yaml.safe_load(Path("specs/contracts/api.yaml").read_text())['api']
db  = yaml.safe_load(Path("specs/contracts/db.yaml").read_text())['db']
ui  = yaml.safe_load(Path("specs/contracts/ui.yaml").read_text())['ui']

rq = {r['id']: {"api": 0, "db": 0, "ui": 0} for r in req}
for a in api:
    for rid in a.get('req', []):
        if rid in rq: rq[rid]['api'] += 1
for d in db:
    for rid in d.get('req', []):
        if rid in rq: rq[rid]['db'] += 1
for u in ui:
    for rid in u.get('req', []):
        if rid in rq: rq[rid]['ui'] += 1

missing = [rid for rid, v in rq.items() if max(v.values()) == 0]
print(json.dumps({"coverage": rq, "missing": missing}, ensure_ascii=False, indent=2))
sys.exit(1 if missing else 0)
""")

# ------------------------------------------------------------
# 5) Evidence/OTEL middleware stubs
# ------------------------------------------------------------
W("server/middleware/otel.py", r"""
# Minimal stub; integrate OpenTelemetry SDK where available
from __future__ import annotations
from typing import Callable
from fastapi import FastAPI, Request


def instrument_app(app: FastAPI) -> None:
    @app.middleware("http")
    async def _otel(request: Request, call_next: Callable):
        # place for traces/metrics; add request-id, timing, etc.
        response = await call_next(request)
        return response
""")

W("grounded/evidence_gate.py", r"""
from __future__ import annotations
from typing import Dict, Any, List

class EvidenceGate:
    def __init__(self, allow_domains: List[str], nli_threshold: float = 0.72, require_provenance: bool = True):
        self.allow = set((allow_domains or []))
        self.thr = nli_threshold
        self.require = require_provenance

    def _allowed(self, src: str) -> bool:
        src = (src or '').lower()
        return any(src.endswith(d.lower()) for d in self.allow) if self.allow else False

    def check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sources = payload.get('sources') or []
        if self.require and not sources:
            return {"ok": False, "reason": "no_provenance"}
        if self.allow:
            for s in sources:
                if not self._allowed(s.get('domain','')):
                    return {"ok": False, "reason": "domain_not_allowed", "bad": s}
        # NLI stub: assume entailment=1.0 if sources exist
        entail = 1.0 if sources else 0.0
        return {"ok": (entail >= self.thr), "entailment": entail}
""")

W("server/middleware/trustops.py", r"""
from __future__ import annotations
from fastapi import FastAPI, Request
from typing import Callable
import yaml
from pathlib import Path
from grounded.evidence_gate import EvidenceGate


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
            # only enforce for JSON responses with declared provenance field
            if resp.media_type == "application/json":
                body = b"".join([chunk async for chunk in resp.body_iterator])
                import json
                data = json.loads(body.decode("utf-8")) if body else {}
                if isinstance(data, dict) and ("sources" in data or pol["grounding"].get("require_provenance", True)):
                    res = gate.check(data)
                    if not res.get("ok"):
                        from starlette.responses import JSONResponse
                        return JSONResponse({"error": "EvidenceGate", "details": res}, status_code=412)
                from starlette.responses import JSONResponse
                return JSONResponse(data)
        except Exception:
            return resp
        return resp
""")

# ------------------------------------------------------------
# 6) gen_universal.py — prefer interview seeds if exist
# ------------------------------------------------------------
W("gen_universal.py", r"""
#!/usr/bin/env python3
from __future__ import annotations
import sys, json
from pathlib import Path
from planner_v2.pipeline import compile_spec
from builder_v2.generate import generate_from_spec


def _has_interview():
    return Path("specs/requirements.yaml").exists()


def main():
    if _has_interview():
        from interview.adapter import load_from_interview
        nl, personas, flows, arch_pref, seeds = load_from_interview()
        spec = compile_spec(nl, personas, flows, arch_pref=arch_pref, seeds=seeds)
    else:
        nl = sys.argv[1] if len(sys.argv) > 1 else "Manage leads and opportunities; add products and checkout."
        personas = ["לקוחות קצה", "צוות פנימי"]; flows = ["יצירת ליד", "הזמנה/תשלום"]
        spec = compile_spec(nl, personas, flows, arch_pref=None)

    Path(".imu_runs").mkdir(exist_ok=True)
    Path(".imu_runs/spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_from_spec(spec)
    print("[OK] generated from planner seeds.")

if __name__ == "__main__":
    main()
""")

# ------------------------------------------------------------
# 7) Default policy/corpora if missing (do not overwrite)
# ------------------------------------------------------------
W("policy/trustops.yaml", """
grounding:
  allow_domains: ["docs.example.com", "regulator.gov"]
  nli_threshold: 0.72
  require_provenance: true
cost:
  max_usd_per_call: 0.02
approvals:
  merge_required: ["owner"]
""", overwrite=False)

W("corpora/allowlist.yaml", """
internal: []
regulatory: []
ttl: 30d
""", overwrite=False)

# ------------------------------------------------------------
# 8) Makefile + README
# ------------------------------------------------------------
W("Makefile", r"""
.PHONY: interview trace plan build run

interview:
	@python interview/engine.py || true

trace:
	@python traceability/trace_gate.py

plan:
	@python gen_universal.py

build: plan  ## alias (builder writes artifacts)

run:
	@uvicorn services.backend.app:app --port 8000 --reload
""")

W("README_M1.md", """
# IMU M1 Fixpack — Quickstart

```bash
python IMU_M1_FIXPACK.py
# 1) Run human interview (if not done):
python interview/engine.py
# 2) Enforce minimal traceability before build (fails if missing):
python traceability/trace_gate.py
# 3) Plan & build from seeds (uses interview outputs if present):
python gen_universal.py
# 4) Run API (health):
make run
```

What you gained:
- Interview → seeds → planner_v2 → builder_v2 (one consistent Spec)
- Evidence/Cost/Allowlist stubs wired via middleware (upgradeable to real NLI/OTEL)
- REQ↔Artifacts coverage gate (CI‑ready)
- Multi‑provider LLM gateway abstraction with cost accounting stubs
""")

print("[OK] IMU M1 FIXPACK written. Run: python IMU_M1_FIXPACK.py")
