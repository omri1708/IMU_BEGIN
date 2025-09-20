# dev consumer using redis.asyncio (no aioredis)
import asyncio, json, os
import redis.asyncio as redis

STREAM   = "items-deleted"
GROUP    = "items-consumers"
CONSUMER = "c1"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def main():
    r = await redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await r.xgroup_create(name=STREAM, groupname=GROUP, id="$", mkstream=True)
    except Exception:
        pass
    print(f"Listening on {STREAM} as {GROUP}/{CONSUMER}")
    while True:
        res = await r.xreadgroup(GROUP, CONSUMER, streams={STREAM: ">"}, count=10, block=5000)
        for _, entries in res or []:
            for entry_id, fields in entries:
                try:
                    print("got", entry_id, json.dumps(fields, ensure_ascii=False))
                finally:
                    await r.xack(STREAM, GROUP, entry_id)
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())
