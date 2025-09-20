# ops/budget_guard.py
from __future__ import annotations
import os, json, sys, time, pathlib

LOG = pathlib.Path(".imu_runs/llm_kpis.jsonl")

def _utc_day(ts): 
    t = time.gmtime(ts); return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
def _utc_month(ts):
    t = time.gmtime(ts); return f"{t.tm_year:04d}-{t.tm_mon:02d}"

def main():
    day_cap  = float(os.getenv("BUDGET_DAILY_USD"  , "2.0"))   # גבול יומי
    mon_cap  = float(os.getenv("BUDGET_MONTHLY_USD", "20.0"))  # גבול חודשי
    if not LOG.exists():
        print(json.dumps({"note":"no llm_kpis.jsonl yet","budget":"ok"}))
        return 0

    today = _utc_day(time.time())
    thism = _utc_month(time.time())
    day_sum = mon_sum = 0.0

    for ln in LOG.read_text(encoding="utf-8").splitlines():
        try:
            j = json.loads(ln); ts = float(j.get("ts",0.0)); c = float(j.get("cost", j.get("cost_usd",0.0)))
        except Exception:
            continue
        if _utc_month(ts) == thism: mon_sum += c
        if _utc_day(ts)   == today: day_sum += c

    out = {"day": day_sum, "day_cap": day_cap, "month": mon_sum, "month_cap": mon_cap}
    ok  = (day_sum <= day_cap) and (mon_sum <= mon_cap)
    print(json.dumps({"budget":"ok" if ok else "exceeded", **out}, ensure_ascii=False))
    sys.exit(0 if ok else 2)

if __name__ == "__main__":
    sys.exit(main())
