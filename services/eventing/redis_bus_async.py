# services/eventing/redis_bus_async.py
from __future__ import annotations
import os, json, asyncio
from redis.asyncio import from_url as redis_from_url

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def _publish_async(stream: str, payload: dict):
    # from_url מחזיר אובייקט Redis אסינכרוני (לא awaitable)
    r = redis_from_url(REDIS_URL, decode_responses=True)
    try:
        # שומרים תאימות לאחור עם "json", ובנוסף חושפים event_id כשדה טופ-לבל לדה-דופ יציב
        fields = {"json": json.dumps(payload, ensure_ascii=False)}

        # אם ה-Producer הזריק event_id לרשומה (כפי שעשינו ב-/debug/outbox/flush) – נשלח אותו טופ-לבל
        event_id = payload.get("event_id")
        if event_id is not None:
            fields["event_id"] = str(event_id)

        # אופציונלי (דיבוג/תצפית): נחשוף חלק מהשדות השכיחים גם למעלה
        for k in ("type", "item_id", "id"):
            if k in payload and k not in fields:
                fields[k] = str(payload[k])

        await r.xadd(stream, fields)
    finally:
        await r.aclose()

def publish_sync(stream: str, payload: dict):
    # מאפשר לקרוא מתוך endpoint סינכרוני
    asyncio.run(_publish_async(stream, payload))

