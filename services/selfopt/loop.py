from __future__ import annotations
import json, pathlib, time
from services.llm.selector import BanditSelector

KPI = pathlib.Path('.imu_runs/llm_kpis.jsonl')


def run_once():
    sel = BanditSelector(KPI)
    # just touch the selector to refresh its priors from KPI log
    return {"arms": {str(k): vars(v) for k, v in sel.arms.items()}}

if __name__ == '__main__':
    while True:
        state = run_once()
        print({"updated": True, "arms": list(state["arms"].keys())})
        time.sleep(60)
