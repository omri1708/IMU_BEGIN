#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gate Audit Max — 100pt rubric, SARIF/JSON/Markdown outputs, actionable remediation.
Scans: .github/workflows, specs/*, policies/*, sos/*, services/*, ops/*, tests/*, packs/*.
Usage:
  python ops/gate_audit_max.py --md ops/audit.md --json ops/audit.json --sarif ops/audit.sarif
Exit codes:
  0 = OK (>=85), 1 = Warn (70..84), 2 = Fail (<70) or blocking rule failed.
"""
from __future__ import annotations
import os, re, json, sys, argparse, pathlib, hashlib
from typing import Dict, Any, List
try:
    import yaml  # pyyaml optional but recommended
except Exception:
    yaml = None

ROOT = pathlib.Path(".").resolve()
WF   = ROOT/".github/workflows"

def read_txt(p: pathlib.Path) -> str:
    try: return p.read_text(encoding="utf-8", errors="ignore")
    except Exception: return ""

def yload(p: pathlib.Path) -> dict:
    if not yaml: return {}
    try: return yaml.safe_load(read_txt(p)) or {}
    except Exception: return {}

def glob(pat: str) -> List[pathlib.Path]:
    return list(ROOT.glob(pat))

def exists(*paths: str) -> bool:
    return all((ROOT/p).exists() for p in paths)

def grep(regex: str, text: str, flags=re.I|re.M) -> bool:
    return re.search(regex, text, flags) is not None

# ---------------- Rules config ----------------
# כל כלל מחזיר (score, max, findings:list[str], remediation:list[str], blocking:bool)
Rule = Dict[str, Any]
RULES: Dict[str, Rule] = {}

def add_rule(key: str, title: str, weight: int, fn, blocking: bool=False):
    RULES[key] = {"title": title, "weight": weight, "fn": fn, "blocking": blocking}

# ---------------- Implementations ----------------
def r_spec_trace() -> Rule:
    score=0; maxp=15; findings=[]; fix=[]
    if exists("specs/requirements.yaml","specs/arch.yaml"):
        score+=6
        reqs=yload(ROOT/"specs/requirements.yaml")
        if reqs.get("requirements"): score+=2
    if exists("specs/contracts/api.yaml"): score+=2
    # REQ tags inside code/tests
    code = "\n".join(read_txt(p) for p in glob("**/*.py"))
    if grep(r"REQ-\d+", code): score+=2
    tests = [p for p in glob("tests/**/*.py") if re.search(r"accept|contract|e2e", p.name, re.I)]
    if tests: score+=3
    else: fix.append("הוסף בדיקות Acceptance/Contract שנגזרות מה-REQs.")
    return score, maxp, findings, fix

def r_grounding_nli() -> Rule:
    score=0; maxp=15; findings=[]; fix=[]
    # Evidence gate in HTTP
    gate_py = ""
    for p in glob("trustops/grounding/*.py"):
        gate_py += read_txt(p)
    if grep(r"EvidenceGate|grounded_strict|enforce_answer", gate_py): score+=6
    else: fix.append("הוסף EvidenceGate לכל יציאה HTTP (No-Evidence→No-Output).")
    # NLI required
    if grep(r"NLI_REQUIRED\s*=\s*['\"]?1['\"]?|os\.getenv\(\s*[\"']NLI_REQUIRED", gate_py):
        score+=4
    else:
        fix.append("חייב NLI per-claim בפרוד (NLI_REQUIRED=1) ללא fallback.")
    # Provenance: TTL + allowlist
    prov_txt = read_txt(ROOT/"grounded/source_policy.py") + read_txt(ROOT/"grounded/provenance_store.py")
    if grep(r"allow|policy|ttl", prov_txt): score+=3
    else: fix.append("הגדר allowlist ו-TTL ב-Provenance (מקורות/דומיינים מאושרים בלבד).")
    # WS gating
    ws_txt = read_txt(ROOT/"chat_api_ws.py")
    if "sources_required" in ws_txt or "grounding" in ws_txt: score+=2
    else: fix.append("ודא ש-WS דורש מקורות (No-Evidence→No-Output) ומפעיל Gate בסיום הזרם.")
    return score, maxp, findings, fix

def r_streaming_alignment() -> Rule:
    score=0; maxp=8; findings=[]; fix=[]
    prod = read_txt(ROOT/"trustops/streaming/producer.py")
    if grep(r"Queue\(maxsize\s*=\s*1[0-9]", prod): score+=2    # back-pressure
    if "cite" in prod or "alignment" in prod: score+=2          # citations
    if any((ROOT/p).exists() for p in ["trustops/alignment/selector.py","trustops/alignment/embeddings.py"]): score+=2
    else: fix.append("הוסף שכבת Alignment (native/embeddings/heuristic) עם citations per token/chunk.")
    if grep(r"StreamPolicyError|enforce_answer|grounding_fail", prod): score+=2
    return score, maxp, findings, fix

def r_domain_opa() -> Rule:
    score=0; maxp=10; findings=[]; fix=[]
    if (ROOT/"policies").exists() and list((ROOT/"policies").rglob("*.rego")):
        score+=5
    else: fix.append("הוסף OPA/Rego למדיניות דומיינית (ABAC/Consent/RLS/Retention).")
    if exists("trustops/domain/abac.py"): score+=3
    if any("retention" in read_txt(p).lower() for p in glob("policies/**/*.rego")): score+=2
    return score, maxp, findings, fix

def r_sre_load() -> Rule:
    score=0; maxp=10; findings=[]; fix=[]
    slo = yload(ROOT/"specs/arch.yaml") if (ROOT/"specs/arch.yaml").exists() else {}
    if slo.get("slo") or slo.get("sli"): score+=2
    if exists("ops/loadgen.py","ops/sre_gate.py"): score+=4
    if (WF.exists() and any(grep(r"sre|load", read_txt(p)) for p in WF.glob("*.yml"))): score+=4
    else: fix.append("הוסף SRE Gate ל-CI (run loadgen + השווה ל-SLO/SLI).")
    return score, maxp, findings, fix

def r_finops_hybrid() -> Rule:
    score=0; maxp=12; findings=[]; fix=[]
    if exists("specs/finops.yaml"): score+=3
    if exists("ops/cost_collector.py","ops/finops_gate.py"): score+=4
    if exists("ops/cost_cloud_collectors.py","ops/cost_unifier.py","ops/finops_hybrid_gate.py"): score+=3
    if (WF.exists() and any("finops" in p.name.lower() for p in WF.glob("*.yml"))): score+=2
    else: fix.append("הוסף FinOps Hybrid Gate (LLM+Infra) ל-CI.")
    return score, maxp, findings, fix

def r_compliance_privacy() -> Rule:
    score=0; maxp=10; findings=[]; fix=[]
    if exists("services/backend/privacy.py") or exists("trustops/compliance/pii.py"): score+=3
    if exists("trustops/compliance/dlp_logging.py","trustops/compliance/lineage.py"): score+=3
    if (WF.exists() and any("compliance" in p.name.lower() for p in WF.glob("*.yml"))): score+=2
    if any("consent" in read_txt(p).lower() for p in glob("**/*.py")): score+=2
    else: fix.append("הוסף DSAR/Consent/Retention Gates ובדיקות רלוונטיות.")
    return score, maxp, findings, fix

def r_security() -> Rule:
    score=0; maxp=8; findings=[]; fix=[]
    all_py = "\n".join(read_txt(p) for p in glob("**/*.py"))
    if "TRUSTOPS_HMAC_KEY" in all_py: score+=2
    if WF.exists() and any(grep(r"sbom|scan", read_txt(p)) for p in WF.glob("*.yml")): score+=3
    # hardcoded secrets?
    if grep(r"(?i)(api[-_]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}", all_py):
        fix.append("זוהו סודות קשיחים בקוד – העבר ל-Vault/ENV והוסף סריקה ב-CI.")
    else:
        score+=3
    return score, maxp, findings, fix

def r_provisioning() -> Rule:
    score=0; maxp=8; findings=[]; fix=[]
    if any((ROOT/p).exists() for p in ["terraform","kustomize","charts"]): score+=3
    if exists("ops/provision_orchestrator.py"): score+=2
    # Plan→Approve→Apply in workflows
    text = "\n".join(read_txt(p) for p in (WF.glob("*.yml") if WF.exists() else []))
    if grep(r"workflow_dispatch|pull_request", text) and grep(r"environment:\s*(dev|staging|prod)", text):
        score+=3
    else:
        fix.append("וודא ש-Apply מתבצע רק ב-env עם approvals (Plan→Approve→Apply).")
    return score, maxp, findings, fix

def r_sot_fhir_hl7() -> Rule:
    score=0; maxp=12; findings=[]; fix=[]
    if exists("sos/sources_of_truth.yaml"): score+=4
    if any("FHIR" in p.parts or "Healthcare" in p.parts for p in glob("packs/**/full/blueprint.yaml")): score+=4
    if exists("integration/hl7/mappings.yaml"): score+=4
    else: fix.append("הוסף מיפויי HL7v2↔FHIR ו-SoT manifest למקורות EHR.")
    return score, maxp, findings, fix

def r_observability() -> Rule:
    score=0; maxp=8; findings=[]; fix=[]
    if exists("charts/observability"): score+=3
    if any("opentelemetry" in read_txt(p).lower() for p in glob("**/*.py")): score+=3
    if (ROOT/"charts/observability/dashboards").exists(): score+=2
    else: fix.append("הוסף דשבורדים ל-Grafana (SLO/SLI, Gates).")
    return score, maxp, findings, fix

# register
add_rule("spec_trace",         "Spec & Traceability",                 15, r_spec_trace)
add_rule("grounding_nli",      "Grounding/NLI Everywhere",            15, r_grounding_nli, blocking=True)
add_rule("stream_align",       "Streaming & Alignment",                8, r_streaming_alignment)
add_rule("domain_opa",         "Domain Policies (OPA/ABAC/RLS)",     10, r_domain_opa)
add_rule("sre_load",           "SRE/Load & SLO Gates",               10, r_sre_load)
add_rule("finops",             "FinOps Hybrid (LLM+Cloud Bills)",    12, r_finops_hybrid)
add_rule("compliance",         "Compliance/Privacy/DSAR/DLP",        10, r_compliance_privacy)
add_rule("security",           "Security (HMAC/SBOM/Secrets)",        8, r_security)
add_rule("provisioning",       "Provisioning (Plan→Approve→Apply)",   8, r_provisioning)
add_rule("sot_health",         "SoT/FHIR/HL7 (Healthcare)",          12, r_sot_fhir_hl7)
add_rule("observability",      "Observability (OTEL/Grafana)",        8, r_observability)

# ---------------- Runner ----------------
def run_audit() -> Dict[str, Any]:
    report={"rules":{}, "score":0, "max":sum(r["weight"] for r in RULES.values()), "remediation":[]}
    blocking_failed=False
    for key, rule in RULES.items():
        s,maxp,find,fix = rule["fn"]()
        # normalize to weight
        weight = rule["weight"]
        norm   = round(min(s, maxp) / maxp * weight)
        report["rules"][key] = {"title":rule["title"], "raw":s, "raw_max":maxp, "score":norm, "weight":weight, "findings":find, "fix":fix, "blocking":rule.get("blocking",False)}
        report["score"] += norm
        if rule.get("blocking") and norm < int(0.6*weight):  # מתחת ל-60% בכלל חסימה
            blocking_failed=True
            report["remediation"].extend(fix)
    report["blocking_failed"]=blocking_failed
    return report

def to_markdown(rep: Dict[str,Any]) -> str:
    lines=[]
    lines.append(f"# Gate Audit Max — {rep['score']}/{rep['max']}")
    if rep.get("blocking_failed"): lines.append("> **Blocking rule failed** – חובה תיקון לפני Merge.")
    lines.append("\n| תחום | ניקוד | משקל |")
    lines.append("|---|---:|---:|")
    for k,v in rep["rules"].items():
        lines.append(f"| {v['title']} | {v['score']} | {v['weight']} |")
    if rep["remediation"]:
        lines.append("\n## Remediations (ממוקדות)")
        for r in sorted(set(rep["remediation"])):
            lines.append(f"- {r}")
    return "\n".join(lines)

def to_sarif(rep: Dict[str,Any]) -> dict:
    # SARIF v2.1.0 – מיפוי כל Rule לאזהרות
    results=[]
    for k,v in rep["rules"].items():
        if v["score"] >= int(0.8*v["weight"]): continue
        level="error" if (v["blocking"] and v["score"]<int(0.6*v["weight"])) else ("warning" if v["score"]<int(0.6*v["weight"]) else "note")
        msg = v["title"] + " — " + "; ".join(v["fix"] or ["שפר עמידה בכללי השער."])
        results.append({
            "ruleId": k,
            "level": level,
            "message": {"text": msg},
            "locations": [{"physicalLocation":{"artifactLocation":{"uri": "."}}}]
        })
    return {"version":"2.1.0","$schema":"https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0-rtm.5.json",
            "runs":[{"tool":{"driver":{"name":"GateAuditMax","informationUri":"https://example.com","rules":[]}}, "results":results}]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--json", help="Path to JSON report")
    ap.add_argument("--md",   help="Path to Markdown report")
    ap.add_argument("--sarif",help="Path to SARIF file")
    rep = run_audit()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if ap.parse_args().json:
        pathlib.Path(ap.parse_args().json).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(ap.parse_args().json).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    if ap.parse_args().md:
        pathlib.Path(ap.parse_args().md).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(ap.parse_args().md).write_text(to_markdown(rep), encoding="utf-8")
    if ap.parse_args().sarif:
        pathlib.Path(ap.parse_args().sarif).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(ap.parse_args().sarif).write_text(json.dumps(to_sarif(rep), ensure_ascii=False, indent=2), encoding="utf-8")
    # Exit code policy
    score = rep["score"]; maxp=rep["max"]; block=rep["blocking_failed"]
    pct = (score/maxp)*100
    code = 2 if (block or pct<70) else (1 if pct<85 else 0)
    sys.exit(code)

if __name__=="__main__":
    main()
