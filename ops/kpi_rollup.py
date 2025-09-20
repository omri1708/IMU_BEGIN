# ops/kpi_rollup.py
from __future__ import annotations
import os, json, time, pathlib, argparse, datetime as dt

LOG = pathlib.Path(".imu_runs/llm_kpis.jsonl")

def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="ops/rollup.json")
    ap.add_argument("--env", default=os.getenv("IMU_ENV", "dev"))
    args = ap.parse_args()

    by_day = {}
    month_total = 0.0
    today = _day(time.time())
    month_prefix = today[:7]  # YYYY-MM

    if LOG.exists():
        for ln in LOG.read_text(encoding="utf-8").splitlines():
            try:
                j = json.loads(ln)
            except Exception:
                continue
            ts = float(j.get("ts", time.time()))
            d = _day(ts)
            cost = float(j.get("cost_usd", j.get("cost", 0.0)) or 0.0)
            by_day[d] = by_day.get(d, 0.0) + cost
            if d.startswith(month_prefix):
                month_total += cost

    out = {
        "env": args.env,
        "today": today,
        "day_cost": round(by_day.get(today, 0.0), 6),
        "month_cost": round(month_total, 6),
        "by_day": {k: round(v, 6) for k, v in sorted(by_day.items())},
    }
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
