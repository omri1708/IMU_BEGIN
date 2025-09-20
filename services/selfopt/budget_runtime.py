# services/selfopt/budget_runtime.py
from __future__ import annotations
import os, json, time, pathlib

LOG = pathlib.Path(".imu_runs/llm_kpis.jsonl")

def _utc_day(ts): 
    t=time.gmtime(ts); return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
def _utc_month(ts):
    t=time.gmtime(ts); return f"{t.tm_year:04d}-{t.tm_mon:02d}"

def read_spend() -> dict:
    """קורא את יומן ה-KPI ומחזיר סכום יומי וחודשי מול תקרות מה-ENV."""
    day_cap  = float(os.getenv("BUDGET_DAILY_USD"  , "1.00"))
    mon_cap  = float(os.getenv("BUDGET_MONTHLY_USD", "10.00"))
    today = _utc_day(time.time())
    thism = _utc_month(time.time())
    day_sum = mon_sum = 0.0

    if LOG.exists():
        for ln in LOG.read_text(encoding="utf-8").splitlines():
            try:
                j=json.loads(ln); ts=float(j.get("ts",0.0)); c=float(j.get("cost", j.get("cost_usd",0.0)))
            except Exception:
                continue
            if _utc_month(ts)==thism: mon_sum += c
            if _utc_day(ts)==today:   day_sum += c

    return {
        "day": round(day_sum,6),
        "day_cap": day_cap,
        "month": round(mon_sum,6),
        "month_cap": mon_cap,
        "ok": (day_sum <= day_cap) and (mon_sum <= mon_cap),
    }

class BudgetExceeded(RuntimeError): ...

def enforce() -> None:
    st = read_spend()
    if not st["ok"]:
        raise BudgetExceeded(f"budget exceeded: day={st['day']}/{st['day_cap']} month={st['month']}/{st['month_cap']}")
