from __future__ import annotations
import json

# Simple guard: require acceptance pass + error budget not exceeded

def decide(accept_pass: bool, err_rate: float, p95_ms: float, slo_ms: float = 800) -> dict:
    ok = accept_pass and err_rate < 0.02 and p95_ms <= slo_ms
    return {'deploy': ok, 'reason': 'ok' if ok else 'slo/acceptance not met'}
