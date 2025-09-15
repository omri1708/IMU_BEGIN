from __future__ import annotations
import yaml, pathlib, textwrap
from sqlalchemy import CheckConstraint

BACK = pathlib.Path('services/backend'); WEB = pathlib.Path('web/next/pages')

T_APP = '''from fastapi import FastAPI
from server.middleware.otel import instrument_app
from server.middleware.trustops import attach_trustops
from server.middleware.redaction import attach_redaction

app = FastAPI(title="Universal App")
instrument_app(app)
attach_trustops(app)
attach_redaction(app)

@app.get('/healthz')
def health():
    return {"ok": True}
'''

T_MODEL_HDR = '''from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, CheckConstraint, UniqueConstraint
Base = declarative_base()
'''

T_MODEL_ROW = ""class {cls}(Base):
    __tablename__ = '{tbl}'
{cols}
    __table_args__ = (
{tbl_args}
    )
""

T_COL = "    {name} = Column({type}{opts})\n"

T_API_HDR = '''from fastapi import APIRouter, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List
from . import models

DB_URL = 'sqlite:///./app.db'
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

router = APIRouter(prefix='/api')
'''

T_API_CRUD = ""
@router.post('/{route}', response_model=dict)
def create_{route}(req: Request):
    role = req.headers.get('X-Role','user')
    data = await req.json()
    obj = models.{cls}(**data)
    db = SessionLocal(); db.add(obj); db.commit(); db.refresh(obj)
    return {{"id": getattr(obj, 'id', None)}}

@router.get('/{route}', response_model=list)
async def list_{route}(req: Request):
    db = SessionLocal(); rows = db.query(models.{cls}).all()
    def pick(r):
        return {{k: getattr(r, k) for k in item_fields}}
    return [pick(r) for r in rows]
""

T_MAIN_INCLUDE = ""
from .api import router as api_router
app.include_router(api_router)
""

T_NEXT_IDX = "export default function Home(){return <main>Home</main>}\n"


def _py(s: str) -> str: return textwrap.dedent(s).lstrip('\n')

def _sqlatype(col):
    t = (col.get('type') or 'str')
    if 'int' in t:   return 'Integer'
    if 'float' in t or 'num' in t: return 'Float'
    if 'text' in t:  return 'Text'
    return 'String'


def write_backend(contracts: dict):
    BACK.mkdir(parents=True, exist_ok=True)
    (BACK/'app.py').write_text(_py(T_APP), encoding='utf-8')
    models_py = [T_MODEL_HDR]
    api_py = [T_API_HDR]

    for ent in contracts.get('db', []):
        tbl = ent['table']; cls = ''.join([p.capitalize() for p in tbl.split('_')])
        cols_py = []
        fields = []
        tbl_args = []
        uniques = []
        for c in ent.get('columns', []):
            name = c['name']
            cons = c.get('constraints',{})
            typ = _sqlatype(c)
            opts = ''
            # String length from max (if numeric and string type)
            if typ == 'String' and isinstance(cons.get('max'), (int,float)):
                opts = f'(int({int(cons["max"])}) )'  # hint length (not strict in sqlite)
                opts = ''
            # nullability
            if cons.get('required', False):
                opts += ', nullable=False'
            # uniqueness
            if cons.get('unique', False):
                opts += ', unique=True'
            # primary key
            if c.get('pk'): opts += ', primary_key=True'
            cols_py.append(T_COL.format(name=name, type=typ, opts=opts))
            # DB CHECK constraints for min/max numeric
            if typ in ('Integer','Float'):
                if cons.get('min') is not None:
                    tbl_args.append(f"CheckConstraint('{name} >= {float(cons['min'])}')")
                if cons.get('max') is not None:
                    tbl_args.append(f"CheckConstraint('{name} <= {float(cons['max'])}')")
            if not c.get('pk'):
                fields.append(name)
        if uniques:
            for u in uniques:
                tbl_args.append(f"UniqueConstraint('{u}')")
        if not tbl_args:
            tbl_args_txt = ''
        else:
            tbl_args_txt = '        ' + ',\n        '.join(tbl_args) + ',\n'
        models_py.append(T_MODEL_ROW.format(cls=cls, tbl=tbl, cols=''.join(cols_py), tbl_args=tbl_args_txt))
        api_py.append('item_fields = '+str(fields)+'\n')
        api_py.append(T_API_CRUD.format(cls=cls, route=tbl))

    (BACK/'models.py').write_text(_py(''.join(models_py)), encoding='utf-8')
    (BACK/'api.py').write_text(_py(''.join(api_py)), encoding='utf-8')
    with (BACK/'app.py').open('a', encoding='utf-8') as f: f.write(_py(T_MAIN_INCLUDE))


def write_ui_stub():
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB/'index.tsx').write_text(T_NEXT_IDX, encoding='utf-8')


def write_iac_stub():
    values = pathlib.Path('charts/imu/values.yaml'); values.parent.mkdir(parents=True, exist_ok=True)
    values.write_text('service: { port: 8000 }\n', encoding='utf-8')


def generate_from_spec(spec: dict):
    write_backend(spec.get('contracts', {}))
    write_ui_stub()
    write_iac_stub()
    pathlib.Path('.imu_runs/spec.json').parent.mkdir(parents=True, exist_ok=True)
    import json
    pathlib.Path('.imu_runs/spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
