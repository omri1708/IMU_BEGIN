#!/usr/bin/env python3
from __future__ import annotations
import sys, json
from pathlib import Path
from planner_v2.pipeline import compile_spec
from builder_v2.generate import generate_from_spec


def _has_interview():
    return Path("specs/requirements.yaml").exists()


def main():
    if _has_interview():
        from interview.adapter import load_from_interview
        nl, personas, flows, arch_pref, seeds = load_from_interview()
        spec = compile_spec(nl, personas, flows, arch_pref=arch_pref, seeds=seeds)
    else:
        nl = sys.argv[1] if len(sys.argv) > 1 else "Manage leads and opportunities; add products and checkout."
        personas = ["לקוחות קצה", "צוות פנימי"]; flows = ["יצירת ליד", "הזמנה/תשלום"]
        spec = compile_spec(nl, personas, flows, arch_pref=None)

    Path(".imu_runs").mkdir(exist_ok=True)
    Path(".imu_runs/spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_from_spec(spec)
    print("[OK] generated from planner seeds.")

if __name__ == "__main__":
    main()
