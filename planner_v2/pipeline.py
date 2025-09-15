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
