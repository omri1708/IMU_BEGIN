# services/eventing/idempotency_store.py
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

def _canonical_json(obj: Dict[str, Any]) -> str:
    # Stable, deterministic JSON for hashing
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def compute_dedup_key(stream: str, fields: Dict[str, Any]) -> str:
    # Prefer explicit event_id if present
    event_id = fields.get("event_id") or fields.get("id")
    if isinstance(event_id, str) and event_id:
        base = f"{stream}|event_id|{event_id}"
    else:
        base = f"{stream}|{_canonical_json(fields)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

class IdempotencyStore(ABC):
    @abstractmethod
    async def is_done(self, stream: str, key: str) -> bool: ...
    @abstractmethod
    async def reserve(self, stream: str, key: str, ttl_seconds: int) -> bool: ...
    @abstractmethod
    async def mark_done(self, stream: str, key: str, ttl_seconds: int) -> None: ...
    @abstractmethod
    async def release_reservation(self, stream: str, key: str) -> None: ...

# ---------------- Redis backend ----------------
try:
    from redis import asyncio as aioredis  # redis>=4.2
except Exception:  # pragma: no cover - import optional
    aioredis = None  # type: ignore

class RedisIdempotencyStore(IdempotencyStore):
    def __init__(self, redis_client: "aioredis.Redis"):
        self.r = redis_client

    def _k_proc(self, stream: str, key: str) -> str:
        return f"idem:{stream}:processing:{key}"

    def _k_done(self, stream: str, key: str) -> str:
        return f"idem:{stream}:done:{key}"

    async def is_done(self, stream: str, key: str) -> bool:
        return bool(await self.r.exists(self._k_done(stream, key)))

    async def reserve(self, stream: str, key: str, ttl_seconds: int) -> bool:
        # SET NX EX → true if acquired
        return await self.r.set(self._k_proc(stream, key), "1", nx=True, ex=ttl_seconds) is True

    async def mark_done(self, stream: str, key: str, ttl_seconds: int) -> None:
        p = self.r.pipeline()
        p.delete(self._k_proc(stream, key))
        p.set(self._k_done(stream, key), "1", ex=ttl_seconds)
        await p.execute()

    async def release_reservation(self, stream: str, key: str) -> None:
        await self.r.delete(self._k_proc(stream, key))

# ---------------- SQLite backend ----------------

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS consumed_messages (
    stream TEXT NOT NULL,
    dedup_key TEXT NOT NULL,
    status TEXT NOT NULL,           -- 'processing' or 'done'
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (stream, dedup_key)
);
"""

class SQLiteIdempotencyStore(IdempotencyStore):
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute(_SQLITE_SCHEMA)
            c.commit()

    def _exec(self, query: str, params: tuple = ()) -> None:
        with sqlite3.connect(self.path) as c:
            c.execute(query, params)
            c.commit()

    def _fetchone(self, query: str, params: tuple = ()) -> Optional[tuple]:
        with sqlite3.connect(self.path) as c:
            cur = c.execute(query, params)
            return cur.fetchone()

    async def is_done(self, stream: str, key: str) -> bool:
        def _op():
            row = self._fetchone(
                "SELECT status FROM consumed_messages WHERE stream=? AND dedup_key=?",
                (stream, key),
            )
            return bool(row and row[0] == "done")
        return await asyncio.to_thread(_op)

    async def reserve(self, stream: str, key: str, ttl_seconds: int) -> bool:
        now = int(time.time())
        def _op():
            try:
                self._exec(
                    "INSERT INTO consumed_messages(stream, dedup_key, status, updated_at) "
                    "VALUES (?, ?, 'processing', ?)",
                    (stream, key, now),
                )
                return True
            except sqlite3.IntegrityError:
                # Exists: check status; if processing and stale by TTL → take over
                row = self._fetchone(
                    "SELECT status, updated_at FROM consumed_messages "
                    "WHERE stream=? AND dedup_key=?",
                    (stream, key),
                )
                if not row:
                    return False
                status, updated_at = row
                if status == "done":
                    return False
                if status == "processing" and now - updated_at > ttl_seconds:
                    # stale reservation → take over
                    self._exec(
                        "UPDATE consumed_messages SET updated_at=? WHERE stream=? AND dedup_key=?",
                        (now, stream, key),
                    )
                    return True
                return False
        return await asyncio.to_thread(_op)

    async def mark_done(self, stream: str, key: str, ttl_seconds: int) -> None:
        now = int(time.time())
        def _op():
            self._exec(
                "UPDATE consumed_messages SET status='done', updated_at=? "
                "WHERE stream=? AND dedup_key=?",
                (now, stream, key),
            )
        await asyncio.to_thread(_op)

    async def release_reservation(self, stream: str, key: str) -> None:
        now = int(time.time())
        def _op():
            self._exec(
                "UPDATE consumed_messages SET updated_at=? "
                "WHERE stream=? AND dedup_key=?",
                (now, stream, key),
            )
        await asyncio.to_thread(_op)

def build_store(
    kind: str,
    redis_client: Optional["aioredis.Redis"] = None,
    sqlite_path: Optional[str] = None,
) -> IdempotencyStore:
    if kind == "redis":
        if aioredis is None or redis_client is None:
            raise RuntimeError("redis backend requested but redis client not provided")
        return RedisIdempotencyStore(redis_client)
    if kind == "sqlite":
        if not sqlite_path:
            raise RuntimeError("sqlite backend requires sqlite_path")
        return SQLiteIdempotencyStore(sqlite_path)
    raise ValueError(f"unknown store kind: {kind}")
