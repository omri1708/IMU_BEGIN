from __future__ import annotations
import os, json, time
from datetime import datetime
from sqlalchemy import create_engine, text
import redis

DB_URL=os.getenv("DATABASE_URL","sqlite:////app/app.db")  # בתוך הקונטיינר המיקום הוא /app/app.db
REDIS_URL=os.getenv("REDIS_URL","redis://redis:6379/0")
STREAM=os.getenv("OUTBOX_STREAM","items-deleted")

def main(loop_sleep=1.0, batch=100):
    r = redis.from_url(REDIS_URL)
    eng = create_engine(DB_URL)
    while True:
        with eng.begin() as conn:
            rows = conn.execute(text(
                "SELECT id, action, status, item_id, payload FROM outbox WHERE status='pending' ORDER BY id ASC LIMIT :n"
            ), {"n": batch}).mappings().all()
            for row in rows:
                evt = json.loads(row["payload"]) if row["payload"] else {"id": row["item_id"], "what": row["action"], "ts": time.time()}
                # כתיבה ל-Redis Stream
                r.xadd(STREAM, {"json": json.dumps(evt, ensure_ascii=False)})
                # סימון כ-sent
                conn.execute(text("UPDATE outbox SET status='sent', sent_at=:ts WHERE id=:id"),
                             {"ts": datetime.utcnow(), "id": row["id"]})
        time.sleep(loop_sleep)

if __name__=="__main__":
    main()
