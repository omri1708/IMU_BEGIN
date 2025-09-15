#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal Interview Bootstrap — full & focused
---------------------------------------------
Creates a human-first, adaptive interview with a pre‑interview (tone/profile),
core blocking Qs (minimum to proceed), and optional deepening sections.
Outputs:
  - interview/flow.yaml        ← interview spec (questions, mapping, gates)
  - interview/engine.py        ← CLI runner with gating, defaults ledger, deepening
  - (on run) specs/*, policy/*, corpora/*, approvals/*, secrets/*, .imu_runs/*

Usage after generation:
  python interview/engine.py

This file just writes the artifacts above.
"""

from __future__ import annotations
import os, pathlib, textwrap
R = pathlib.Path(".").resolve()

def W(rel: str, s: str, mode: int = 0o644) -> None:
    p = R / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(s).lstrip("\n"), encoding="utf-8")
    os.chmod(p, mode)

# 1) Flow YAML — human questions, mapping to tech, gates & levels
W("interview/flow.yaml", """
version: 1
core_min:
  # minimal set required to start building specs safely (blocking)
  - use_case
  - personas
  - flows
  - cloud_pref

sections:
  - id: onboarding
    title: "ראיון מקדים — איך לדבר איתך"
    level: pre
    questions:
      - id: profile_name
        label: "איך לפנות אליך? (שם פרטי)"
        type: text
        default: "חבר/ה"
        map_to: ui.profile.name
      - id: language
        label: "באיזו שפה להציג לך?"
        type: choice
        options: ["עברית","English"]
        default: "עברית"
        map_to: ui.profile.language
      - id: tone
        label: "איזה סגנון מתאים?"
        type: choice
        options: ["ידידותי/אנושי","עסקי/רשמי","טכני"]
        default: "ידידותי/אנושי"
        map_to: ui.profile.tone
      - id: verbosity
        label: "כמה לפרט בתשובות?"
        type: choice
        options: ["תמציתי","רגיל","מפורט"]
        default: "רגיל"
        map_to: ui.profile.verbosity
      - id: visuals
        label: "להעדיף נקודות/טבלאות/דיאגרמות כשאפשר?"
        type: choice
        options: ["כן","לא"]
        default: "כן"
        map_to: ui.profile.visuals
      - id: followups_opt_in
        label: "תרצה שנציע העמקה עם שאלות קצרות רק כשזה חשוב?"
        type: choice
        options: ["כן","לא"]
        default: "כן"
        map_to: ui.profile.followups

  - id: domain
    title: "הקשר עסקי"
    level: core
    questions:
      - id: use_case
        label: "מה את/ה רוצה שהמערכת תעשה? (במילים פשוטות)"
        help: "משפט או שניים. בלי מונחים טכניים."
        type: text
        required: true
        gate: blocking
        map_to: requirements.explicit
      - id: personas
        label: "מי ישתמש בזה? (פרסונות עיקריות)"
        type: multiselect
        options: ["לקוחות קצה","צוות פנימי","שותפים","מנהלים","אחר"]
        default: ["לקוחות קצה"]
        required: true
        gate: blocking
        map_to: requirements.personas
      - id: flows
        label: "מהן 2–3 הזרימות החשובות?"
        help: "דוגמה: 'הזמנה→תשלום→חשבונית', 'פנייה→טיפול→סגירה'."
        type: textarea
        required: true
        gate: blocking
        map_to: requirements.flows
      - id: industry
        label: "באיזה תחום? (אם רלוונטי)"
        type: text
        default: "כללי"
        map_to: requirements.industry

  - id: features
    title: "יכולות"
    level: optional
    questions:
      - id: auth_model
        label: "אימות והרשאות"
        type: choice
        options: ["JWT בסיסי","SSO/OIDC (כניסה עם Google/IdP)","שניהם","לא יודע/ת"]
        default: "JWT בסיסי"
        map_to: contracts.auth.type
      - id: multitenant
        label: "רב-דייריות (לקוחות/ארגונים נפרדים)?"
        type: choice
        options: ["כן","לא","לא יודע/ת"]
        default: "לא"
        map_to: arch.constraints.multitenant
      - id: payments
        label: "תשלומים/גבייה נדרשים?"
        type: choice
        options: ["כן (Stripe)","לא","לא יודע/ת"]
        default: "לא"
        map_to: contracts.payments.provider
      - id: search
        label: "חיפוש מתקדם?"
        type: choice
        options: ["כן (OpenSearch)","בסיסי","לא","לא יודע/ת"]
        default: "בסיסי"
        map_to: contracts.search.level
      - id: notifications
        label: "התראות (מייל/פוש/ווב-הוקים)?"
        type: multiselect
        options: ["Email","Push","Webhooks","אין צורך"]
        default: ["Email"]
        map_to: contracts.notifications.channels
      - id: audit_logs
        label: "נדרש יומן פעולות (Audit Log)?"
        type: choice
        options: ["כן","לא","לא יודע/ת"]
        default: "כן"
        map_to: contracts.audit_log.enabled

  - id: nonfunc
    title: "איכות ואילוצים"
    level: optional
    questions:
      - id: p95
        label: "יעד ביצועים (p95_latency_ms)"
        type: choice
        options: ["<=400","<=800","<=1500","לא יודע/ת"]
        default: "<=800"
        map_to: arch.slo.p95_latency_ms
      - id: ok_rate
        label: "יעד זמינות/הצלחה (OK rate)"
        type: choice
        options: [">=0.99",">=0.995",">=0.997","לא יודע/ת"]
        default: ">=0.99"
        map_to: arch.sli.http_ok_rate
      - id: data_classes
        label: "איזה סוגי מידע רגישים יש? (אם יש)"
        type: multiselect
        options: ["אין","Email","טלפון","אמצעי תשלום","בריאות","מקום","אחר"]
        default: ["אין"]
        map_to: arch.constraints.pii_classes

  - id: cloud
    title: "ענן/סביבה (אנושי, לא טכני)"
    level: core
    questions:
      - id: cloud_pref
        label: "איפה תרצה להריץ את זה?"
        type: choice
        options: ["AWS","GCP","Azure","On-Prem","לא יודע/ת"]
        default: "AWS"
        required: true
        gate: blocking
        map_to: arch.cloud
      - id: envs
        label: "באילו סביבות עובדים?"
        type: multiselect
        options: ["dev","staging","prod"]
        default: ["dev","staging"]
        map_to: arch.environments
      - id: data_residency
        label: "מיקום נתונים נדרש? (למשל EU/IL/US)"
        type: text
        default: "N/A"
        map_to: arch.constraints.data_residency

  - id: policies
    title: "מדיניות ו‑TrustOps"
    level: optional
    questions:
      - id: evidence_mode
        label: "עד כמה להקשיח הוכחות (Evidence‑Gate)?"
        type: choice
        options: ["מחמיר (Strict)","רגיל (Standard)","כבוי (Off)"]
        default: "מחמיר (Strict)"
        map_to: policy.trustops.evidence_mode
      - id: cost_budget
        label: "תקציב מקס׳ לשיחה ל‑LLM (USD)"
        type: choice
        options: ["0.005","0.01","0.02","0.05","לא יודע/ת"]
        default: "0.02"
        map_to: policy.cost.max_usd_per_call
      - id: allow_web
        label: "מותר להיעזר באינטרנט?"
        type: choice
        options: ["רק מקורות שלי","גם אתרים מאושרים","לא יודע/ת"]
        default: "רק מקורות שלי"
        map_to: policy.grounding.web_mode
      - id: allow_domains
        label: "אם אינטרנט: אילו דומיינים? (פסיקים/שורות)"
        type: textarea
        map_to: policy.grounding.allow_domains

  - id: corpora
    title: "מקורות וקורפוסים"
    level: optional
    questions:
      - id: internal_sources
        label: "אילו מקורות פנימיים רלוונטיים? (קישורים/תיקיות)"
        type: textarea
        map_to: corpora.internal
      - id: regulatory_sources
        label: "רגולציה/נהלים שחייבים להישען עליהם?"
        type: textarea
        map_to: corpora.regulatory
      - id: corpora_ttl
        label: "תוקף ברירת מחדל למסמכים (TTL)"
        type: choice
        options: ["7d","30d","90d"]
        default: "30d"
        map_to: corpora.ttl

  - id: approvals
    title: "אישורים ושערים"
    level: optional
    questions:
      - id: approver_role
        label: "מי מאשר לפני פריסה ל‑prod?"
        type: choice
        options: ["אני","מנהל מוצר","QA","משפטי/רגולציה","אין"]
        default: "אני"
        map_to: policy.approvals.merge.required
      - id: risk_level
        label: "רמת סיכון/רגישות"
        type: choice
        options: ["נמוכה","בינונית","גבוהה"]
        default: "בינונית"
        map_to: policy.risk.level

  - id: ux
    title: "חוויית משתמש"
    level: optional
    questions:
      - id: ux_nav
        label: "מפת מסכים ראשונית"
        type: textarea
        map_to: ui.sitemap
      - id: tone_override
        label: "טון לתוכן המוצר (אם שונה מהכללי)"
        type: choice
        options: ["כמו בראיון המקדים","עסקי/רשמי","ידידותי/אנושי","טכני"]
        default: "כמו בראיון המקדים"
        map_to: ui.tone
""")

# 2) Engine — CLI with gates, ledger, deepening, YAML-safe dump
W("interview/engine.py", r"""
from __future__ import annotations
import pathlib, sys, json, re

FLOW   = pathlib.Path("interview/flow.yaml")
STATE  = pathlib.Path(".imu_runs/state.json")
TRANS  = pathlib.Path(".imu_runs/interview_transcript.md")
ASSUME = pathlib.Path(".imu_runs/assumptions.jsonl")

# ---------- YAML helpers ----------

def safe_dump_yaml(obj) -> str:
    try:
        import yaml  # type: ignore
        return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)
    except Exception:
        return json.dumps(obj, ensure_ascii=False, indent=2)

def write_yaml(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(safe_dump_yaml(obj), encoding="utf-8")

# ---------- Flow/State ----------

def load_flow():
    import yaml  # required at runtime
    return yaml.safe_load(FLOW.read_text(encoding="utf-8"))

def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"answers": {}, "progress": [], "profile": {}}

def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- UX ----------

def say(txt: str):
    print(txt)

def log_assumption(qid: str, label: str, provided, default):
    used_default = (provided == default)
    ASSUME.parent.mkdir(parents=True, exist_ok=True)
    with ASSUME.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"qid": qid, "label": label, "value": provided,
                            "default": default, "used_default": used_default}, ensure_ascii=False) + "\n")

# ---------- Asking ----------

def ask(q: dict, idx: int, total: int):
    print(f"\n[{idx}/{total}] {q.get('label','שאלה')}")
    if q.get("help"): print(f"(למה שואלים? {q['help']})")
    t = q.get("type", "text")
    default = q.get("default")
    options = q.get("options", [])
    if t in ("choice", "multiselect") and options:
        for i, opt in enumerate(options, start=1):
            print(f"  {i}. {opt}")
        print("  0. לא יודע/ת  (נבחר דיפולט בטוח)")
    print("פקודות: /back (חזור), /skip (דילוג בטוח), /quit (יציאה), /more (העמקה)")

    while True:
        ans = input("> ").strip()
        if ans == "/quit":
            sys.exit(0)
        if ans == "/back":
            return "__BACK__"
        if ans == "/more":
            return "__MORE__"
        if ans == "/skip" or ans == "0" or ans.lower() == "לא יודע/ת":
            return default
        if t in ("text", "textarea"):
            return ans or default
        if t == "choice":
            if ans.isdigit() and 1 <= int(ans) <= len(options):
                return options[int(ans) - 1]
            if ans:
                return ans  # free-form "other"
        if t == "multiselect":
            if ans:
                try:
                    idxs = [int(x) for x in re.split(r"[ ,;]+", ans) if x]
                    vals = [options[i - 1] for i in idxs if 1 <= i <= len(options)]
                    return vals or default
                except Exception:
                    return [ans]  # treat as custom value
            return default

# ---------- Core gating ----------

def core_min_ids(flow: dict) -> list[str]:
    return list(flow.get("core_min", []) or [])


def is_core_satisfied(flow: dict, st: dict) -> bool:
    need = set(core_min_ids(flow))
    have = set(k for k, v in st["answers"].items() if v not in (None, "", []))
    return need.issubset(have)


# ---------- Mapping answers → specs/policy/etc ----------

def set_in(d: dict, path: str, value):
    keys = path.split(".")
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def normalize_listish(val):
    if val is None:
        return []
    if isinstance(val, str):
        # split by newline or comma
        parts = [x.strip() for x in re.split(r"[\n,]", val) if x.strip()]
        return parts
    if isinstance(val, list):
        return val
    return [val]


def parse_flows(val):
    items = normalize_listish(val)
    # also split by arrows if a single line with arrows
    out = []
    for it in items:
        if "→" in it or "->" in it:
            out.append(it)
        elif it:
            out.append(it)
    return out or ["זרימה כללית"]


def map_answers_to_specs(flow: dict, st: dict) -> dict:
    answers = st["answers"]
    specs = {
        "requirements": {"requirements": []},
        "arch": {"architecture": "monolith", "slo": {}, "sli": {}, "constraints": {}, "environments": ["dev", "staging"]},
        "contracts": {},
        "ui": {},
        "policy": {"trustops": {}, "grounding": {}, "approvals": {}, "cost": {}, "risk": {}},
        "corpora": {},
    }

    # apply map_to from flow
    for sec in flow["sections"]:
        for q in sec.get("questions", []):
            m = q.get("map_to")
            if not m:
                continue
            qid = q["id"]
            val = answers.get(qid)
            if val is None:
                continue
            set_in(specs, m, val)

    # Build requirements from explicit + flows
    use_case = answers.get("use_case")
    flows = parse_flows(answers.get("flows"))
    reqs = []
    if use_case:
        reqs.append({"id": "REQ-001", "title": str(use_case), "explicit": [str(use_case)], "implicit": [],
                     "priority": {"moscow": "should", "rice": {"reach": 70, "impact": 2, "confidence": 0.7, "effort": 2, "score": 49}}})
    for i, f in enumerate(flows, start=2):
        reqs.append({"id": f"REQ-{i:03d}", "title": f, "explicit": [f], "implicit": [],
                     "priority": {"moscow": "should", "rice": {"reach": 60, "impact": 2, "confidence": 0.7, "effort": 2, "score": 42}}})
    if not reqs:
        reqs = [{"id": "REQ-001", "title": "High-level goal", "explicit": ["High-level goal"], "implicit": [],
                 "priority": {"moscow": "should", "rice": {"reach": 50, "impact": 2, "confidence": 0.6, "effort": 2, "score": 30}}}]
    specs["requirements"]["requirements"] = reqs

    # Arch defaults / parsing numbers
    p95 = answers.get("p95", "<=800")
    m = re.match(r"<=\s*(\d+)", str(p95) or "")
    if m:
        specs["arch"]["slo"]["p95_latency_ms"] = int(m.group(1))
    okr = answers.get("ok_rate", ">=0.99")
    m2 = re.match(r">=\s*(0\.\d+)", str(okr) or "")
    if m2:
        specs["arch"]["sli"]["http_ok_rate"] = float(m2.group(1))

    envs = answers.get("envs") or ["dev", "staging"]
    specs["arch"]["environments"] = envs

    # Policy/TrustOps from answers
    evidence_mode = answers.get("evidence_mode", "מחמיר (Strict)")
    nli_threshold = {"מחמיר (Strict)": 0.78, "רגיל (Standard)": 0.72, "כבוי (Off)": 0.0}.get(evidence_mode, 0.72)
    specs["policy"]["trustops"]["nli_threshold"] = nli_threshold
    specs["policy"]["trustops"]["require_provenance"] = (evidence_mode != "כבוי (Off)")

    budget = answers.get("cost_budget") or "0.02"
    try:
        specs["policy"]["cost"]["max_usd_per_call"] = float(budget)
    except Exception:
        specs["policy"]["cost"]["max_usd_per_call"] = 0.02

    web_mode = answers.get("allow_web", "רק מקורות שלי")
    specs["policy"]["grounding"]["web_allowed"] = (web_mode != "רק מקורות שלי")
    allow_domains = normalize_listish(answers.get("allow_domains"))
    specs["policy"]["grounding"]["allow_domains"] = allow_domains

    approver = answers.get("approver_role", "אני")
    specs["policy"]["approvals"]["merge_required"] = [approver] if approver and approver != "אין" else []
    specs["policy"]["risk"]["level"] = answers.get("risk_level", "בינונית")

    # Corpora
    specs["corpora"]["internal"] = normalize_listish(answers.get("internal_sources"))
    specs["corpora"]["regulatory"] = normalize_listish(answers.get("regulatory_sources"))
    specs["corpora"]["ttl"] = answers.get("corpora_ttl", "30d")

    # UI profile
    specs["ui"]["profile"] = {
        "name": st.get("profile", {}).get("name") or answers.get("profile_name", "חבר/ה"),
        "language": answers.get("language", "עברית"),
        "tone": answers.get("tone", "ידידותי/אנושי"),
        "verbosity": answers.get("verbosity", "רגיל"),
        "visuals": answers.get("visuals", "כן"),
        "followups": answers.get("followups_opt_in", "כן"),
    }

    return specs

# ---------- Writers ----------

def write_specs(specs: dict):
    base = pathlib.Path("specs")
    (base / "contracts").mkdir(parents=True, exist_ok=True)
    # requirements
    write_yaml(base / "requirements.yaml", {"requirements": specs["requirements"]["requirements"]})
    # arch
    write_yaml(base / "arch.yaml", {
        "architecture": specs["arch"].get("architecture", "monolith"),
        "slo": specs["arch"].get("slo", {}),
        "sli": specs["arch"].get("sli", {}),
        "constraints": specs["arch"].get("constraints", {}),
        "environments": specs["arch"].get("environments", ["dev", "staging"]),
    })
    # contracts skeleton (derived lightly from first REQ/flow)
    reqs = specs["requirements"]["requirements"]
    main_req = reqs[0]["id"] if reqs else "REQ-001"
    apis = [
        {"id": "API-001", "req": [main_req], "path": "/items", "method": "POST", "acceptance": ["200 + persisted"]},
        {"id": "API-002", "req": [main_req], "path": "/items", "method": "GET",  "acceptance": ["200 + list"]},
    ]
    db = [
        {"id": "DB-001", "req": [main_req], "table": "items",
         "columns": [{"name": "id", "type": "int", "pk": True}, {"name": "name", "type": "str"}, {"name": "description", "type": "text"}]}
    ]
    ui = [
        {"id": "UI-001", "req": [main_req], "screen": "Items", "route": "/items", "acceptance": ["Create + List"]},
    ]
    write_yaml(base / "contracts" / "api.yaml", {"api": apis})
    write_yaml(base / "contracts" / "db.yaml",  {"db": db})
    write_yaml(base / "contracts" / "ui.yaml",  {"ui": ui})


def write_policy(specs: dict):
    pol = pathlib.Path("policy")
    pol.mkdir(parents=True, exist_ok=True)
    trustops = {
        "grounding": {
            "allow_domains": specs["policy"]["grounding"].get("allow_domains", []),
            "web_allowed": specs["policy"]["grounding"].get("web_allowed", False),
            "nli_threshold": specs["policy"]["trustops"].get("nli_threshold", 0.72),
            "require_provenance": specs["policy"]["trustops"].get("require_provenance", True),
        },
        "cost": {
            "max_usd_per_call": specs["policy"]["cost"].get("max_usd_per_call", 0.02)
        },
        "approvals": specs["policy"].get("approvals", {}),
        "risk": specs["policy"].get("risk", {}),
    }
    write_yaml(pol / "trustops.yaml", trustops)


def write_corpora(specs: dict):
    base = pathlib.Path("corpora")
    (base / "index").mkdir(parents=True, exist_ok=True)
    allow = {
        "internal": specs.get("corpora", {}).get("internal", []),
        "regulatory": specs.get("corpora", {}).get("regulatory", []),
        "ttl": specs.get("corpora", {}).get("ttl", "30d"),
    }
    write_yaml(base / "allowlist.yaml", allow)


def write_approvals(specs: dict):
    base = pathlib.Path("approvals")
    base.mkdir(parents=True, exist_ok=True)
    write_yaml(base / "merge_guard.yaml", specs["policy"].get("approvals", {}))


def write_secrets_manifest(specs: dict):
    base = pathlib.Path("secrets")
    base.mkdir(parents=True, exist_ok=True)
    envs = specs.get("arch", {}).get("environments", ["dev", "staging"])
    sm = {
        "env": {"IMU_ENV": envs[0], "TRUSTOPS_HMAC_KEY": "<64hex>", "JWT_SECRET": "<change-me>"},
        "llm": {"OPENAI_API_KEY": "<opt>"},
        "kubernetes": {"KUBE_CONFIG_DEV_B64": "<opt>"},
        "datastores": {"DB_URL": "sqlite:///./app.db", "REDIS_URL": "redis://localhost:6379/0"},
    }
    write_yaml(base / "manifest.yaml", sm)


def write_transcript(st: dict):
    ans = st["answers"]
    lines = ["# תמליל הראיון (תקציר)", ""]
    for k, v in ans.items():
        lines.append(f"- **{k}**: {v}")
    TRANS.parent.mkdir(parents=True, exist_ok=True)
    TRANS.write_text("\n".join(lines), encoding="utf-8")

# ---------- Runner ----------

def flatten_questions(flow: dict):
    qs = []
    for sec in flow["sections"]:
        for q in sec.get("questions", []):
            qs.append((sec, q))
    return qs


def run_section(flow: dict, st: dict, section_id: str) -> None:
    sec = next((s for s in flow["sections"] if s["id"] == section_id), None)
    if not sec:
        return
    qs = sec.get("questions", [])
    total = len(qs)
    i = 0
    while i < total:
        q = qs[i]
        qid = q["id"]
        # skip if already answered and not required to reconfirm
        if qid in st["answers"] and st["answers"][qid] not in (None, "", []):
            i += 1
            continue
        ans = ask(q, i + 1, total)
        if ans == "__BACK__":
            if i > 0:
                i -= 1
            else:
                say("כבר בתחילת הסקשן.")
            continue
        if ans == "__MORE__":
            # break out to deepening menu without losing place
            st["progress"] = st.get("progress", []) + [f"more@{section_id}:{qid}"]
            save_state(st)
            deepening_menu(flow, st)
            continue
        st["answers"][qid] = ans
        log_assumption(qid, q.get("label", qid), ans, q.get("default"))
        st["progress"] = st.get("progress", []) + [qid]
        save_state(st)
        i += 1


def run_onboarding(flow: dict, st: dict):
    run_section(flow, st, "onboarding")
    # cache profile
    st["profile"] = {
        "name": st["answers"].get("profile_name", "חבר/ה"),
        "language": st["answers"].get("language", "עברית"),
        "tone": st["answers"].get("tone", "ידידותי/אנושי"),
        "verbosity": st["answers"].get("verbosity", "רגיל"),
        "visuals": st["answers"].get("visuals", "כן"),
        "followups": st["answers"].get("followups_opt_in", "כן"),
    }
    save_state(st)


def run_core(flow: dict, st: dict):
    # ask only blocking questions from 'domain' and 'cloud'
    for sec_id in ("domain", "cloud"):
        sec = next((s for s in flow["sections"] if s["id"] == sec_id), None)
        if not sec:
            continue
        core_qs = [q for q in sec.get("questions", []) if q.get("gate") == "blocking"]
        total = len(core_qs)
        i = 0
        while i < total:
            q = core_qs[i]
            qid = q["id"]
            if qid in st["answers"] and st["answers"][qid] not in (None, "", []):
                i += 1
                continue
            ans = ask(q, i + 1, total)
            if ans == "__BACK__":
                if i > 0:
                    i -= 1
                else:
                    say("כבר בתחילת הסקשן.")
                continue
            if ans == "__MORE__":
                st["progress"] = st.get("progress", []) + [f"more@{sec_id}:{qid}"]
                save_state(st)
                deepening_menu(flow, st)
                continue
            st["answers"][qid] = ans
            log_assumption(qid, q.get("label", qid), ans, q.get("default"))
            st["progress"] = st.get("progress", []) + [qid]
            save_state(st)
            i += 1


def deepening_menu(flow: dict, st: dict):
    if st.get("profile", {}).get("followups", "כן") != "כן":
        return
    topics = [
        ("features", "יכולות"),
        ("nonfunc", "איכות ואילוצים"),
        ("policies", "מדיניות ו‑TrustOps"),
        ("corpora", "מקורות וקורפוסים"),
        ("approvals", "אישורים ושערים"),
        ("ux", "חוויית משתמש"),
    ]
    say("\nהגענו לסף המינימלי לריצה. תרצה/י להעמיק באחד הנושאים?")
    for i, (_, title) in enumerate(topics, start=1):
        say(f"  {i}. {title}")
    say("  0. המשך ללא העמקה")

    sel = input("> נושא לבחירה (מספרים מופרדים בפסיקים): ").strip()
    if not sel or sel == "0":
        return
    try:
        idxs = [int(x) for x in re.split(r"[ ,;]+", sel) if x]
        for idx in idxs:
            if 1 <= idx <= len(topics):
                run_section(flow, st, topics[idx - 1][0])
    except Exception:
        return


def write_all_outputs(flow: dict, st: dict):
    specs = map_answers_to_specs(flow, st)
    write_specs(specs)
    write_policy(specs)
    write_corpora(specs)
    write_approvals(specs)
    write_secrets_manifest(specs)
    write_transcript(st)
    # persist presentation profile for other components
    prof = pathlib.Path("ui/presentation_profile.json")
    prof.parent.mkdir(parents=True, exist_ok=True)
    prof.write_text(json.dumps(specs.get("ui", {}).get("profile", {}), ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    try:
        flow = load_flow()
    except Exception as e:
        print("שגיאה בטעינת flow.yaml — וודא ש-PyYAML מותקן: pip install pyyaml")
        raise

    st = load_state()

    # Pre-interview: tune voice & interaction style
    run_onboarding(flow, st)

    # Core blocking: collect only what's needed to proceed
    run_core(flow, st)

    if not is_core_satisfied(flow, st):
        print("\nלא הושג סף מינימלי (core_min). נא השלם את השאלות החסרות.")
        # offer another pass
        run_core(flow, st)

    # Optional deepening
    deepening_menu(flow, st)

    # Emit outputs
    write_all_outputs(flow, st)

    print("\n[סיום] קבצי Spec/Policy/Corpora/Approvals/Secrets נוצרו. אפשר להתקדם לשלב Traceability & Build.")

if __name__ == "__main__":
    main()
""")

print("נוצרו: interview/flow.yaml, interview/engine.py — להרצה: python interview/engine.py")
