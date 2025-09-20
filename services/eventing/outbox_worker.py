from __future__ import annotations
import json
from services.backend.api import SessionLocal
from services.backend import models

def _send(evt: dict) -> bool:
    # כאן תתחבר בעתיד ל-Kafka/Redis. לעכשיו "נשלח" תמיד.
    # print(f"send:{evt}")
    return True

def flush(limit: int = 100) -> list[dict]:
    db = SessionLocal()
    rows = (db.query(models.Outbox)
              .filter(models.Outbox.status == "pending")
              .order_by(models.Outbox.id).limit(limit).all())
    out=[]
    for r in rows:
        ok = _send(json.loads(r.payload))
        r.status = "sent" if ok else "error"
        out.append({"id": r.id, "ok": ok})
    db.commit()
    return out
