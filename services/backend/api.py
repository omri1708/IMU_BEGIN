from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from . import models
from fastapi import HTTPException, Request
from server.middleware.redaction_core import load_policies, apply_redaction

DB_URL = 'sqlite:///./app.db'
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

router = APIRouter(prefix='/api')

class ItemIn(BaseModel):
    name: str | None = None
    description: str | None = None

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


@router.delete('/items/{item_id}', response_model=dict)
async def delete_items(item_id: int):
    db = SessionLocal()
    row = db.query(models.Items).get(item_id)   # Items הוא השם המחולל למחלקה
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(row)
    db.commit()
    return {"ok": True}

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
