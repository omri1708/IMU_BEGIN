import asyncio
import json
import os
from pathlib import Path
import uuid

import pytest
from redis import asyncio as aioredis

from services.eventing.redis_consumer import build_argparser, consume_once

pytestmark = pytest.mark.skipif(
    not os.environ.get("REDIS_URL"), reason="REDIS_URL not set"
)

STREAM = "items-deleted"
GROUP = "bus-consumers"

async def _ensure_group(r):
    try:
        await r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception:
        pass

@pytest.mark.asyncio
async def test_duplicate_injection_processed_once(tmp_path: Path):
    r = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await _ensure_group(r)
    sink = tmp_path / "sink.jsonl"

    # שתי הודעות זהות עם אותו event_id
    eid = f"eo-{uuid.uuid4()}"
    await r.xadd(STREAM, {"event_id": eid, "type": "item_deleted", "item_id": "555"})
    await r.xadd(STREAM, {"event_id": eid, "type": "item_deleted", "item_id": "555"})

    args = build_argparser().parse_args([
        "--streams", STREAM,
        "--group", GROUP,
        "--count", "200",
        "--metrics-file", str(tmp_path / "m.json"),
        "--sink-path", str(sink),
    ])
    await consume_once(args)

    lines = [json.loads(x) for x in sink.read_text(encoding="utf-8").splitlines()]
    only_555 = [x for x in lines if x["payload"].get("item_id") == "555"]
    assert len(only_555) == 1

    await r.aclose()

@pytest.mark.asyncio
async def test_fail_then_dlq_after_retries(tmp_path: Path):
    r = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await _ensure_group(r)

    # הודעה שתיכשל; נשתמש ב-reclaim כדי לגרום למסירה חוזרת
    eid = f"fail-{uuid.uuid4()}"
    await r.xadd(STREAM, {"event_id": eid, "type": "item_deleted", "item_id": "42", "fail_me": "1"})

    args = build_argparser().parse_args([
        "--streams", STREAM,
        "--group", GROUP,
        "--count", "100",
        "--dlq-threshold", "3",
        "--fail-on-field", "fail_me",
        "--reclaim-idle-ms", "1",         # גורם למסירות חוזרות מיידיות
        "--metrics-file", str(tmp_path / "m.json"),
        "--sink-path", str(tmp_path / "sink.jsonl"),
    ])

    # שלוש איטרציות כדי לעבור את הסף ולהפיל ל-DLQ
    for _ in range(3):
        await consume_once(args)

    dlq = await r.xrevrange(f"{STREAM}-dlq", count=10)
    assert dlq and len(dlq) >= 1, "expected message in DLQ"

    await r.aclose()
