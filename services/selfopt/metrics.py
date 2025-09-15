from __future__ import annotations
import json, time, pathlib

P = pathlib.Path('.imu_runs/metrics.jsonl')

def log(event: str, **kw):
    P.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), "event": event}
    rec.update(kw)
    with P.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
