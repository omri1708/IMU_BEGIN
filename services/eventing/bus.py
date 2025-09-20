# services/eventing/bus.py
from __future__ import annotations
import os, json, datetime, pathlib

class Bus:
    """
    פרסום ל-Redis אם REDIS_URL קיים; אחרת רושם לקובץ .imu_runs/bus_<stream>.jsonl
    """
    def __init__(self):
        self.url = os.getenv("REDIS_URL", "").strip()

    def publish(self, stream: str, msg: dict) -> None:
        if self.url:
            try:
                import redis  # pip install redis
                r = redis.Redis.from_url(self.url)
                # Redis Streams מצפה למפה של מחרוזות
                data = {k: (json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)
                        for k, v in (msg or {}).items()}
                r.xadd(stream, data)
                return
            except Exception:
                pass  # fallback לקובץ
        # קובץ JSONL fallback
        p = pathlib.Path(".imu_runs") / f"bus_{stream}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.datetime.utcnow().isoformat()+"Z", **(msg or {})}
        p.open("a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False)+"\n")
