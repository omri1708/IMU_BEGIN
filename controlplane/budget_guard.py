from __future__ import annotations
import json, sys
# guard: stop pipeline if projected monthly exceeds hard cap
# usage: python budget_guard.py .imu_runs/llm_kpis.jsonl 100.0

def main():
    path = sys.argv[1]; cap = float(sys.argv[2])
    spent = 0.0
    try:
        for line in open(path, encoding='utf-8'):
            try:
                j = json.loads(line); spent += float(j.get('cost', j.get('cost_usd', 0.0)))
            except Exception: pass
    except FileNotFoundError:
        pass
    if spent > cap:
        print(json.dumps({'budget':'exceeded','spent':spent,'cap':cap}))
        raise SystemExit(3)
    print(json.dumps({'budget':'ok','spent':spent,'cap':cap}))

if __name__=='__main__':
    main()
