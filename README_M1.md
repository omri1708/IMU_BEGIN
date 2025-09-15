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
