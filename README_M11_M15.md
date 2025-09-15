# IMU M11–M15 Full-closure Pack

**What you now have:**
- Planner++ that emits contexts/events and acceptance/property tests.
- Builder++ that can generate per-context microservice stubs with OpenAPI/AsyncAPI.
- CI/CD autonomy with auto-patch PRs, canary router, and drift guard.
- Evidence/NLI + citations enforced on HTTP and WS.
- Control-plane sync for prices/tokenizers with budget limits per provider.
- Traceability functional gate.

## Suggested flow
```
# (1) Generate acceptance/property tests
python -c "from planner_advanced.acceptance_gen import gen_acceptance; gen_acceptance()"
python -c "from planner_advanced.prop_tests import gen_property_tests; gen_property_tests()"

# (2) Plan & build from interview seeds
python gen_universal.py
python -m builder_micro.generate_services

# (3) Run tests & auto-patch if needed
pytest -q --maxfail=1 --disable-warnings --junitxml .imu_runs/junit.xml || true
python tests/miner/regression_miner.py .imu_runs/junit.xml || true
python ci/autopatch.py || true

# (4) Enforce traceability + functional gates
python traceability/trace_gate.py
python traceability/functional_gate.py

# (5) Sync control-plane hints
python controlplane/pricing_sync.py
python controlplane/tokenizer_sync.py
```

> **Note:** Real cloud rollout, OAuth handshakes, and provider billing require your secrets and accounts. All components are idempotent and ready for wiring.
