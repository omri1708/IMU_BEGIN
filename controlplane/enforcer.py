from __future__ import annotations
import time, json, pathlib

BUDGET = pathlib.Path('controlplane/rate_budget.yaml')
COUNTER = pathlib.Path('.imu_runs/budget_state.json')

try:
    import yaml
except Exception:
    yaml = None


def _now_month():
    t = time.gmtime()
    return f"{t.tm_year:04d}-{t.tm_mon:02d}"


def _load():
    pol = {'limits': {'default_call_cap_usd': 0.02, 'monthly_cap_usd': 50.0, 'per_provider': {}}}
    if yaml and BUDGET.exists():
        pol = yaml.safe_load(BUDGET.read_text())
    st = {}
    if COUNTER.exists():
        try: st = json.loads(COUNTER.read_text())
        except Exception: st = {}
    return pol, st


def check_and_add(provider: str, cost: float) -> dict:
    pol, st = _load()
    month = _now_month()
    node = st.setdefault(month, {}).setdefault(provider, {'spent': 0.0})
    node['spent'] += float(cost)
    COUNTER.parent.mkdir(parents=True, exist_ok=True)
    COUNTER.write_text(json.dumps(st), encoding='utf-8')
    cap = pol.get('limits', {}).get('per_provider', {}).get(provider, {}).get('cap_usd') or pol.get('limits', {}).get('monthly_cap_usd', 50.0)
    ok = node['spent'] <= float(cap)
    return {'ok': ok, 'spent': node['spent'], 'cap': cap}
