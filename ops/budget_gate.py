# ops/budget_gate.py
from __future__ import annotations
import os, sys, json, yaml, argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollup", default="ops/rollup.json")
    ap.add_argument("--spec",   default="specs/finops.yaml")
    ap.add_argument("--env",    default=os.getenv("IMU_ENV", "dev"))
    args = ap.parse_args()

    try:
        roll = json.loads(open(args.rollup, "r", encoding="utf-8").read())
    except Exception:
        print("[BUDGET] no rollup, treating costs as 0")
        roll = {"day_cost": 0.0, "month_cost": 0.0}

    spec = yaml.safe_load(open(args.spec, "r", encoding="utf-8").read())
    bud = (spec.get("budgets") or {}).get(args.env, {})
    daily = float(bud.get("daily_usd", 999999))
    monthly = float(bud.get("monthly_usd", 999999))

    day = float(roll.get("day_cost", 0.0))
    mon = float(roll.get("month_cost", 0.0))

    ok = (day <= daily) and (mon <= monthly)
    print(json.dumps({
        "env": args.env,
        "day_cost": day, "daily_cap": daily,
        "month_cost": mon, "monthly_cap": monthly,
        "ok": ok
    }, ensure_ascii=False, indent=2))
    sys.exit(0 if ok else 2)

if __name__ == "__main__":
    main()
