# services/eventing/redis_bus_async.py
from __future__ import annotations
import os, json, asyncio
from redis.asyncio import from_url as redis_from_url

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def _publish_async(stream: str, payload: dict):
    r = await redis_from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        # נעטוף JSON תחת שדה יחיד "json" כדי לשמור פורמט עקבי
        await r.xadd(stream, {"json": json.dumps(payload, ensure_ascii=False)})
    finally:
        await r.aclose()

def publish_sync(stream: str, payload: dict):
    # מאפשר לקרוא מתוך endpoint סינכרוני
    asyncio.run(_publish_async(stream, payload))
