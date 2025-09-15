from __future__ import annotations
import asyncio, aioredis
from typing import Any, Dict

class Bus:
    def __init__(self, url: str = 'redis://localhost:6379/0'):
        self.url = url
        self.redis = None
    async def connect(self):
        self.redis = await aioredis.from_url(self.url, decode_responses=True)
    async def publish(self, stream: str, msg: Dict[str,Any]):
        await self.redis.xadd(stream, msg)
    async def consume(self, stream: str, group: str, consumer: str, block_ms: int = 1000):
        try:
            await self.redis.xgroup_create(stream, group, id='$', mkstream=True)
        except Exception:
            pass
        while True:
            res = await self.redis.xreadgroup(group, consumer, streams={stream:'>'}, count=10, block=block_ms)
            for st, entries in res or []:
                for (entry_id, fields) in entries:
                    yield (entry_id, fields)
                    await self.redis.xack(stream, group, entry_id)
