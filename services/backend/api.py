from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from . import models
from fastapi import HTTPException, Request
from server.middleware.redaction_core import load_policies, apply_redaction
import yaml
import os
from pathlib import Path


DB_URL = 'sqlite:///./app.db'
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

router = APIRouter(prefix='/api')

class ItemIn(BaseModel):
    name: str | None = None
    description: str | None = None


def _load_domain_policy():
    p = Path("policy/domain.yaml")
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}

@router.post('/items', response_model=dict)
async def create_items(body: ItemIn):
    db = SessionLocal()
    try:
        obj = models.Items(**{k: v for k, v in body.dict().items() if v is not None})
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return {"id": getattr(obj, 'id', None)}
    finally:
        db.close()

@router.get('/items', response_model=list)
async def list_items():
    db = SessionLocal()
    try:
        rows = db.query(models.Items).all()
        return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]
    finally:
        db.close()

@router.put('/items/{item_id}')
async def update_items(item_id: int, body: dict):
    db = SessionLocal()
    M = models.Items
    row = db.query(M).filter(M.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    for k,v in (body or {}).items():
        if k in ('name','description'):
            setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.delete("/items/{item_id}")
def delete_item(item_id: int, request: Request):
    db = SessionLocal()
    row = db.query(models.Items).get(item_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    pol_all = _load_domain_policy()
    guard = (pol_all.get("delete_guard") or {})

    # 1) חסימה לפי שם
    if row.name in (guard.get("forbidden_names") or []):
        raise HTTPException(status_code=403, detail="forbidden name")

    # 2) דרישת אישור – רק כשמוגדר וגם כשחל על השם
    hdr = guard.get("require_header")
    names_needing_hdr = set(guard.get("header_required_for_names") or [])
    need_header = bool(hdr) and (not names_needing_hdr or row.name in names_needing_hdr)

    if need_header and (request.headers.get(hdr) or "").lower() != "yes":
        raise HTTPException(status_code=403, detail=f"admin approval required (set {hdr}: yes)")

    # 3) כתיבת Outbox (במצב pending)
    import json, time
    evt = {"id": item_id, "what": "item_deleted", "ts": time.time()}
    ob = models.Outbox(
        topic="items",
        key=str(item_id),
        action="deleted",
        status="pending",
        item_id=item_id,
        payload=json.dumps(evt, ensure_ascii=False),
    )
    db.add(ob)

    # 4) מחיקה בפועל
    db.delete(row)
    db.commit()
    return JSONResponse({"ok": True, "id": item_id})

# --- debug PII sample (לבדיקת רדקציה/מדיניות) ---
@router.get("/debug/pii")
def debug_pii(req: Request):
    sample = {
        "email": "demo@example.com",
        "phone": "+1 555 123 4567",
        "credit_card": "4242 4242 4242 4242",
        "note": "This is a non-PII field",
    }
    pii, rbac = load_policies()
    role = req.headers.get("X-Role", "user")
    return apply_redaction(sample, role, pii, rbac)

@router.get("/debug/outbox")
def debug_outbox():
    db = SessionLocal()
    rows = db.query(models.Outbox).order_by(models.Outbox.id.desc()).all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "topic": r.topic or "",                     # ← שדה תצוגה
            "key": (str(r.key) if r.key is not None else ""),  # ← תמיד קיים
            "action": r.action,
            "status": r.status,
            "item_id": r.item_id,
            "payload": r.payload,
            "created_at": str(r.created_at) if r.created_at else None,
            "sent_at": str(r.sent_at) if r.sent_at else None,
        })
    return out

@router.post("/debug/outbox/flush")
def debug_outbox_flush(limit: int = 100):
    from datetime import datetime
    import json, os
    from pathlib import Path

    # file-sink: נשמור שורות JSONL בתיקיית .imu_runs
    sink = os.getenv("BUS_SINK", "file")   # אפשר להחליף ל-redis בהמשך
    bus_dir = Path(".imu_runs")
    bus_dir.mkdir(parents=True, exist_ok=True)
    bus_file = bus_dir / "bus_items-deleted.jsonl"

    db = SessionLocal()
    pending = (db.query(models.Outbox)
                 .filter(models.Outbox.status == "pending")
                 .order_by(models.Outbox.id.asc())
                 .limit(limit)
                 .all())

    cnt = 0
    written = 0
    # נכתוב לקובץ רק אם sink=file
    fp = open(bus_file, "a", encoding="utf-8") if sink == "file" else None
    try:
        for r in pending:
            # "שליחה" לסינק (כאן: קובץ JSONL)
            if fp:
                try:
                    payload = json.loads(r.payload) if r.payload else {}
                except Exception:
                    payload = {"raw": r.payload}

                line = {
                    "topic": r.topic or "items",
                    "key":   r.key or (str(r.item_id) if r.item_id is not None else ""),
                    "action": r.action,
                    "payload": payload,
                }
                fp.write(json.dumps(line, ensure_ascii=False) + "\n")
                written += 1

            # סימון כ־sent
            r.status = "sent"
            r.sent_at = datetime.utcnow()
            cnt += 1
        db.commit()
    finally:
        if fp:
            fp.close()

    return {"flushed": cnt, "bus_file": str(bus_file), "written": written}
