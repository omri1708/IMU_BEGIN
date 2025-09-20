# services/eventing/publisher.py
from __future__ import annotations
import os, json, pathlib, time

BUS_MODE = os.getenv("IMU_BUS", "file").lower()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def _write_file(topic: str, key: str, payload: dict, action: str | None):
    root = pathlib.Path(".imu_runs"); root.mkdir(parents=True, exist_ok=True)
    name = f"bus_{topic}.jsonl"
    rec = {
        "ts": time.time(),
        "topic": topic,
        "action": action or (topic.split("-", 1)[1] if "-" in topic else None),
        "key": key,
        "payload": payload,
    }
    (root / name).open("a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")

async def _write_redis_async(topic: str, key: str, payload: dict, action: str | None):
    import aioredis
    stream = f"bus:{topic}"
    rec = {
        "ts": str(time.time()),
        "topic": topic,
        "action": action or (topic.split("-", 1)[1] if "-" in topic else ""),
        "key": key,
        "payload": json.dumps(payload, ensure_ascii=False),
    }
    r = await aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        await r.xadd(stream, rec)
    finally:
        await r.close()

def publish(topic: str, key: str, payload: dict, action: str | None = None):
    """פרסום סינכרוני. Redis (אם IMU_BUS=redis) או קובץ fallback."""
    if BUS_MODE == "redis":
        try:
            import asyncio
            asyncio.run(_write_redis_async(topic, key, payload, action))
            return
        except Exception:
            # fallback לקובץ אם Redis לא זמין
            pass
    _write_file(topic, key, payload, action)
