from fastapi import APIRouter, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List
from . import models

DB_URL = 'sqlite:///./app.db'
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

router = APIRouter(prefix='/api')
item_fields = ['name', 'description']

@router.post('/entities', response_model=dict)
def create_entities(req: Request):
    role = req.headers.get('X-Role','user')
    data = await req.json()
    obj = models.Entities(**data)
    db = SessionLocal(); db.add(obj); db.commit(); db.refresh(obj)
    return {"id": getattr(obj, 'id', None)}

@router.get('/entities', response_model=list)
async def list_entities(req: Request):
    db = SessionLocal(); rows = db.query(models.Entities).all()
    def pick(r):
        return {k: getattr(r, k) for k in item_fields}
    return [pick(r) for r in rows]
