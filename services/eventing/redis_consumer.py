# services/eventing/redis_consumer.py
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import signal
import socket
import sys
import time
from typing import Any, Dict, List, Tuple

from redis import asyncio as aioredis  # redis>=4.2

from services.eventing.idempotency_store import (
    build_store,
    compute_dedup_key,
    IdempotencyStore,
)

DEFAULT_STREAMS = ["items-deleted"]
DEFAULT_GROUP = "bus-consumers"

log = logging.getLogger("redis_consumer")


class Metrics:
    def __init__(self) -> None:
        self.messages_total = 0
        self.processed = 0
        self.duplicates_skipped = 0
        self.attempts = 0
        self.failed = 0
        self.dlq_published = 0
        self.acks = 0
        self.processing_ms_sum = 0.0

    def avg_ms(self) -> float:
        return (self.processing_ms_sum / self.processed) if self.processed else 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "messages_total": self.messages_total,
            "processed": self.processed,
            "duplicates_skipped": self.duplicates_skipped,
            "attempts": self.attempts,
            "failed": self.failed,
            "dlq_published": self.dlq_published,
            "acks": self.acks,
            "processing_ms_avg": round(self.avg_ms(), 3),
        }


async def ensure_group(r: aioredis.Redis, stream: str, group: str) -> None:
    try:
        await r.xgroup_create(stream, group, id="$", mkstream=True)
        log.info("XGROUP CREATE %s %s", stream, group)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            return
        raise


async def times_delivered(
    r: aioredis.Redis, stream: str, group: str, message_id: str
) -> int:
    # Kept for compatibility/reference; not relied upon for DLQ threshold.
    try:
        res = await r.xpending_range(stream, group, min=message_id, max=message_id, count=1)
        if res:
            entry = res[0]
            count = getattr(entry, "delivery_count", None)
            return int(count if count is not None else entry[4])  # type: ignore[index]
    except Exception:
        pass
    return 1


async def publish_dlq(
    r: aioredis.Redis,
    source_stream: str,
    message_id: str,
    dedup_key: str,
    fields: Dict[str, Any],
    reason: str,
) -> None:
    dlq_stream = f"{source_stream}-dlq"
    payload = {
        "source_stream": source_stream,
        "original_id": message_id,
        "dedup_key": dedup_key,
        "reason": reason,
        "payload": json.dumps(fields, ensure_ascii=False),
        "ts": int(time.time() * 1000),
    }
    await r.xadd(dlq_stream, payload)


def _normalize_xautoclaim_response(resp: Any) -> Tuple[str | None, List[Tuple[str, Dict[str, Any]]]]:
    """
    Normalize redis-py XAUTOCLAIM responses to: (next_id, [(id, dict_fields)]).
    Accepts shapes like:
      - (next_id, [(id, {fields})...])
      - [next_id, [(id, [f1,v1,...])...]]
      - (next_id, [ids...])  # JUSTID
    """
    next_id = None
    messages: List[Tuple[str, Dict[str, Any]]] = []
    if isinstance(resp, (list, tuple)):
        if len(resp) >= 2:
            next_id = resp[0]
            raw = resp[1] or []
        else:
            raw = []
    else:
        raw = []
    for entry in raw:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            mid, fields = entry
            if isinstance(fields, dict):
                messages.append((str(mid), fields))
            elif isinstance(fields, (list, tuple)):
                it = iter(fields)
                d = {k: v for k, v in zip(it, it)}
                messages.append((str(mid), d))
            else:
                messages.append((str(mid), {}))
        elif isinstance(entry, str):
            messages.append((entry, {}))
        else:
            try:
                messages.append((str(entry[0]), {}))
            except Exception:
                pass
    return next_id, messages


async def _incr_attempts(r: aioredis.Redis, stream: str, dedup_key: str, ttl: int) -> int:
    k = f"idem:{stream}:attempts:{dedup_key}"
    val = await r.incr(k)
    try:
        await r.expire(k, ttl)
    except Exception:
        pass
    return int(val)


async def side_effect_write_jsonl(sink_path: str, record: Dict[str, Any]) -> None:
    loop = asyncio.get_running_loop()
    line = json.dumps(record, ensure_ascii=False) + "\n"
    await loop.run_in_executor(None, _append_line, sink_path, line)


def _append_line(path: str, line: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


async def handle_message(
    r: aioredis.Redis,
    store: IdempotencyStore,
    stream: str,
    msg_id: str,
    fields: Dict[str, Any],
    args: argparse.Namespace,
    metrics: Metrics,
) -> None:
    metrics.messages_total += 1
    dedup_key = compute_dedup_key(stream, fields)

    if await store.is_done(stream, dedup_key):
        metrics.duplicates_skipped += 1
        await r.xack(stream, args.group, msg_id)
        metrics.acks += 1
        return

    reserved = await store.reserve(stream, dedup_key, args.processing_ttl_sec)
    if not reserved:
        metrics.duplicates_skipped += 1
        await r.xack(stream, args.group, msg_id)
        metrics.acks += 1
        return

    start = time.perf_counter()
    try:
        if args.fail_on_field and fields.get(args.fail_on_field):
            raise RuntimeError(f"forced failure: {args.fail_on_field}=true")

        record = {
            "stream": stream,
            "id": msg_id,
            "dedup_key": dedup_key,
            "payload": fields,
            "ts": int(time.time() * 1000),
        }
        await side_effect_write_jsonl(args.sink_path, record)

        await store.mark_done(stream, dedup_key, args.done_ttl_sec)
        await r.xack(stream, args.group, msg_id)
        metrics.acks += 1
        metrics.processed += 1
        metrics.processing_ms_sum += (time.perf_counter() - start) * 1000.0

    except Exception as e:
        metrics.failed += 1
        metrics.attempts += 1
        attempts = await _incr_attempts(r, stream, dedup_key, args.done_ttl_sec)
        if attempts >= args.dlq_threshold:
            try:
                await publish_dlq(r, stream, msg_id, dedup_key, fields, reason=str(e))
            finally:
                await r.xack(stream, args.group, msg_id)
                metrics.acks += 1
                metrics.dlq_published += 1
                await store.release_reservation(stream, dedup_key)
        else:
            await store.release_reservation(stream, dedup_key)


async def _claim_pending_and_process(
    r: aioredis.Redis,
    store: IdempotencyStore,
    args: argparse.Namespace,
    metrics: Metrics,
) -> None:
    """Re-delivery of pending messages: XAUTOCLAIM first, fallback to XPENDING→XCLAIM."""
    if not getattr(args, "reclaim_idle_ms", 0):
        return

    for s in args.streams:
        # 1) Try XAUTOCLAIM
        try:
            resp = await r.xautoclaim(
                s,
                args.group,
                args.consumer,
                min_idle_time=args.reclaim_idle_ms,
                start_id="0-0",
                count=args.count,
            )
            _next, claimed = _normalize_xautoclaim_response(resp)
            for msg_id, fields in claimed:
                await handle_message(r, store, s, msg_id, fields, args, metrics)
            if claimed:
                continue  # proceed next stream; we handled re-delivery
        except Exception:
            log.exception("XAUTOCLAIM failed on stream=%s", s)

        # 2) Fallback: XPENDING→XCLAIM
        try:
            pend = await r.xpending_range(s, args.group, min="-", max="+", count=args.count)
            ids: List[str] = []
            for entry in pend or []:
                mid = None
                idle = None
                if hasattr(entry, "message_id"):
                    mid = entry.message_id
                    idle = getattr(entry, "idle", None)
                elif isinstance(entry, (list, tuple)) and len(entry) >= 4:
                    mid = entry[0]
                    idle = entry[2]
                if mid and (idle is None or int(idle) >= int(args.reclaim_idle_ms)):
                    ids.append(str(mid))
            if ids:
                claimed_raw = await r.xclaim(
                    s,
                    args.group,
                    args.consumer,
                    int(args.reclaim_idle_ms),
                    ids,
                )
                _next, claimed = _normalize_xautoclaim_response([None, claimed_raw])
                for msg_id, fields in claimed:
                    await handle_message(r, store, s, msg_id, fields, args, metrics)
        except Exception:
            log.exception("XPENDING/XCLAIM fallback failed on stream=%s", s)


async def consume_once(args: argparse.Namespace) -> Metrics:
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL is not set")

    r = aioredis.from_url(redis_url, decode_responses=True)
    try:
        for s in args.streams:
            await ensure_group(r, s, args.group)

        if args.store == "redis":
            store = build_store("redis", redis_client=r)
        else:
            store = build_store("sqlite", sqlite_path=args.sqlite_path)

        metrics = Metrics()

        # Re-delivery of pending (before reading new messages)
        await _claim_pending_and_process(r, store, args, metrics)

        # Read new messages for this group/consumer
        streams_spec = {s: ">" for s in args.streams}
        results = await r.xreadgroup(
            groupname=args.group,
            consumername=args.consumer,
            streams=streams_spec,
            count=args.count,
            block=args.block_ms,
        )

        for stream, messages in results or []:
            for msg_id, fields in messages:
                await handle_message(
                    r=r,
                    store=store,
                    stream=stream,
                    msg_id=msg_id,
                    fields=fields,
                    args=args,
                    metrics=metrics,
                )

        if args.metrics_file:
            os.makedirs(os.path.dirname(args.metrics_file) or ".", exist_ok=True)
            with open(args.metrics_file, "w", encoding="utf-8") as f:
                json.dump(metrics.as_dict(), f, ensure_ascii=False, indent=2)

        return metrics
    finally:
        await r.aclose()


async def consume_loop(args: argparse.Namespace) -> None:
    stop = asyncio.Event()

    def _graceful(*_: Any) -> None:
        log.info("Shutdown signal received")
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _graceful)
        except NotImplementedError:
            pass

    while not stop.is_set():
        try:
            await consume_once(args)
        except Exception:
            log.exception("consume_once iteration failed")
            await asyncio.sleep(1.0)


def _default_consumer() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("redis-consumer (Exactly-once)")
    p.add_argument("--streams", nargs="+", default=DEFAULT_STREAMS)
    p.add_argument("--group", default=DEFAULT_GROUP)
    p.add_argument("--consumer", default=_default_consumer())
    p.add_argument("--count", type=int, default=100)
    p.add_argument("--block-ms", type=int, default=5000)
    p.add_argument("--dlq-threshold", type=int, default=5)
    p.add_argument("--processing-ttl-sec", type=int, default=600)  # 10m
    p.add_argument("--done-ttl-sec", type=int, default=7 * 24 * 3600)  # 7d
    p.add_argument("--store", choices=["redis", "sqlite"], default="redis")
    p.add_argument("--sqlite-path", default="data/idempotency.db")
    p.add_argument("--sink-path", default="data/sink.jsonl")
    p.add_argument("--metrics-file", default="data/consumer_metrics.json")
    p.add_argument("--loop", action="store_true", help="run as daemon loop")
    p.add_argument("--fail-on-field", default="", help="if field is truthy → fail")
    p.add_argument("--log-level", default="INFO")
    p.add_argument(
        "--reclaim-idle-ms",
        type=int,
        default=0,
        help="If >0, reclaim pending msgs idle >= this (ms) via XAUTOCLAIM/XCLAIM",
    )
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.loop:
        asyncio.run(consume_loop(args))
    else:
        metrics = asyncio.run(consume_once(args))
        log.info("metrics: %s", metrics.as_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
