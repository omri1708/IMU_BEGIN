from __future__ import annotations
from pathlib import Path
import json, time

SPANS = Path('.imu_runs/otel_spans.jsonl')
KPIS  = Path('.imu_runs/llm_kpis.jsonl')  # reuse bandit log for simplicity

# naive aggregator: per route/operation compute latency & error ratio

def _iter_jsonl(p: Path):
    if not p.exists():
        return []
    for line in p.read_text(encoding='utf-8').splitlines():
        try:
            yield json.loads(line)
        except Exception:
            continue

def aggregate():
    buckets = {}
    for rec in _iter_jsonl(SPANS):
        name = rec.get('name','op')
        dur  = max(0, (rec.get('end',0) - rec.get('start',0)) / 1e6)
        err  = 1.0 if 'ERROR' in str(rec.get('status','')).upper() else 0.0
        b = buckets.setdefault(name, {'n':0, 'dur':0.0, 'err':0.0})
        b['n'] += 1; b['dur'] += dur; b['err'] += err
    now = time.time()
    out = []
    for name, b in buckets.items():
        avg_lat = (b['dur']/b['n']) if b['n'] else 0.0
        err_rate = (b['err']/b['n']) if b['n'] else 0.0
        out.append({'ts': now, 'op': name, 'avg_latency_ms': avg_lat, 'error_rate': err_rate})
        # write also to bandit log as synthetic KPI (provider/model unknown here)
        with KPIS.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': now, 'provider': 'otel', 'model': name, 'ptok':0,'ctok':0,
                                'cost':0.0, 'latency_ms': avg_lat, 'ok': (err_rate<0.5)}, ensure_ascii=False)+"\n")
    return out

if __name__ == '__main__':
    res = aggregate()
    print(json.dumps({'ops': len(res)}, ensure_ascii=False))
