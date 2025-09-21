# services/eventing/outbox_worker.py
from __future__ import annotations
import os, json, time, pathlib, datetime as dt
from typing import Any, Dict, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.backend import models

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

RUNS = pathlib.Path(".imu_runs"); RUNS.mkdir(parents=True, exist_ok=True)

def _publish_file(topic: str, action: str, payload: dict):
    p = RUNS / f"bus_{topic}-{action}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as w:
        w.write(json.dumps(payload, ensure_ascii=False) + "\n")

def _publish_redis(topic: str, action: str, payload: dict):
    url = os.getenv("REDIS_URL")
    if not url:
        return
    try:
        import redis  # redis>=5
        r = redis.from_url(url)
        stream = f"{topic}-{action}"
        r.xadd(stream, {"json": json.dumps(payload, ensure_ascii=False)})
    except Exception as e:
        # לא מפיל את ה-flush; נשאר עם קובץ
        print("[outbox->redis] WARN:", e)

def flush_to_bus(limit: int = 100) -> int:
    """
    שולף רשומות pending מה-outbox, מפרסם (קובץ + Redis אם יש), ומסמן sent.
    idempotency: סימון sent מונע שליחה כפולה. אם קרסנו אחרי פרסום ולפני סימון —
    בפעם הבאה יש סיכון לשידור כפול → לכן הצרכן צריך להיות idem-safe (נוסיף בהמשך).
    """
    db = SessionLocal()
    try:
        rows = (db.query(models.Outbox)
                  .filter(models.Outbox.status == "pending")
                  .order_by(models.Outbox.id.asc())
                  .limit(limit).all())
        sent = 0
        for r in rows:
            try:
                payload = json.loads(r.payload or "{}")
            except Exception:
                payload = {"raw": r.payload}
            # הוספת מטא בסיסית
            payload.setdefault("key", r.key or str(r.item_id or ""))
            payload.setdefault("item_id", r.item_id)
            payload.setdefault("ts", time.time())

            _publish_file(r.topic or "items", r.action or "event", payload)
            _publish_redis(r.topic or "items", r.action or "event", payload)

            r.status = "sent"
            r.sent_at = dt.datetime.utcnow()
            sent += 1
        db.commit()
        return sent
    finally:
        db.close()

if __name__ == "__main__":
    n = flush_to_bus(limit=int(os.getenv("OUTBOX_FLUSH_LIMIT", "100")))
    print(json.dumps({"flushed": n}, ensure_ascii=False))
