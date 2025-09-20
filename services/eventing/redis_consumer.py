# services/eventing/redis_consumer.py
from __future__ import annotations
import asyncio, json, os
import redis.asyncio as redis

STREAM = os.getenv("IMU_BUS_STREAM", "items-deleted")
GROUP  = os.getenv("IMU_BUS_GROUP",  "bus-consumers")
NAME   = os.getenv("IMU_BUS_NAME",   "bus-1")

async def main():
    r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"), decode_responses=True)
    try:
        await r.xgroup_create(STREAM, GROUP, id="$", mkstream=True)
    except Exception:
        pass
    print(f"[worker] listening on {STREAM} group={GROUP} name={NAME}")
    while True:
        resp = await r.xreadgroup(GROUP, NAME, {STREAM: ">"}, count=10, block=5000)
        for _stream, entries in resp or []:
            for entry_id, fields in entries:
                try:
                    evt = json.loads(fields.get("json","{}"))
                    # כאן היית עושה side-effect אמיתי (שליחה החוצה, log, וכו')
                    print("[event]", entry_id, evt)
                    await r.xack(STREAM, GROUP, entry_id)
                except Exception as e:
                    print("[event-error]", entry_id, e)
        await asyncio.sleep(0)

if __name__ == "__main__":
    asyncio.run(main())
