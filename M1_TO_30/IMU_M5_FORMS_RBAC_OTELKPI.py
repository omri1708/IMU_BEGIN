#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU M5 — Zod Forms + RBAC‑aware UI + OTEL→KPI + Constraint Interview
-------------------------------------------------------------------
Idempotently *adds/patches* the following so the system enriches itself with the
user **only when needed**, generates **rich forms with Zod** from DB constraints,
**hides/disables fields by role**, and **turns OTEL spans into KPIs** feeding the
Self‑Opt bandit.

Writes/patches:
  interview/constraints_enricher.py     ← asks for missing field constraints, updates specs/contracts/db.yaml
  policy/rbac.yaml                      ← default roles & field‑level visibility/editing
  builder_v2/formgen.py                 ← generates Zod schemas + RHF pages with RBAC
  web/next/lib/rbac.ts                  ← tiny role store (can be swapped to real auth)
  web/next/components/Field.tsx         ← RBAC‑aware, error display, disabled logic
  web/next/pages/_app.tsx               ← RoleProvider wiring (non‑destructive append)
  server/middleware/otel.py             ← add JSONL span exporter alongside OTLP
  services/selfopt/otel_to_kpi.py       ← aggregates spans→KPIs and updates LLM bandit log
  Makefile                              ← targets: forms, enrich, otel_kpi

Usage after creating this file:
  python IMU_M5_FORMS_RBAC_OTELKPI.py
  # (1) If constraints missing →
  make enrich    # guided, only asks when needed
  # (2) Regenerate rich forms
  make forms
  # (3) Run app & collect spans → KPIs
  make run
  make otel_kpi
"""
from __future__ import annotations
import os, pathlib, textwrap, json
R = pathlib.Path('.')

def W(rel: str, s: str, mode: int = 0o644, overwrite: bool = True) -> None:
    p = R/rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not p.exists():
        p.write_text(textwrap.dedent(s).lstrip('\n'), encoding='utf-8'); os.chmod(p, mode)

# ---------------------------------------------------------------------
# 1) Constraint Enricher (asks only when missing)
# ---------------------------------------------------------------------
W('interview/constraints_enricher.py', r"""
from __future__ import annotations
import yaml, sys
from pathlib import Path

def _ask(prompt: str, default: str | None = None) -> str:
    p = f"{prompt} " + (f"[{default}] " if default is not None else '')
    v = input(p).strip()
    return (v or default or '').strip()

def enrich_db_constraints(db_yaml_path: str = 'specs/contracts/db.yaml'):
    p = Path(db_yaml_path)
    if not p.exists():
        print('[enrich] db.yaml not found, nothing to enrich'); return 0
    y = yaml.safe_load(p.read_text())
    changed = False
    for ent in y.get('db', []):
        tbl = ent.get('table')
        for col in ent.get('columns', []):
            cons = col.setdefault('constraints', {})
            needs = []
            if 'required' not in cons: needs.append('required')
            if 'min' not in cons and any(k in (col.get('type','')) for k in ['int','float','num']): needs.append('min')
            if 'max' not in cons and any(k in (col.get('type','')) for k in ['int','float','num']): needs.append('max')
            if 'regex' not in cons and 'str' in (col.get('type','')): needs.append('regex')
            if 'enum' not in cons: needs.append('enum')
            if not needs: continue
            print(f"\n[enrich] {tbl}.{col['name']} (type={col.get('type')}) — missing: {needs}")
            if 'required' in needs:
                ans = _ask('  required? (y/n)', 'y' if not col.get('pk') else 'y')
                cons['required'] = (ans.lower().startswith('y'))
            if 'min' in needs:
                ans = _ask('  min (blank to skip)', '')
                if ans: cons['min'] = float(ans)
            if 'max' in needs:
                ans = _ask('  max (blank to skip)', '')
                if ans: cons['max'] = float(ans)
            if 'regex' in needs and 'str' in (col.get('type','')):
                ans = _ask('  regex (e.g. ^[\\w.-]+@.+$) blank to skip', '')
                if ans: cons['regex'] = ans
            if 'enum' in needs:
                ans = _ask('  enum values (comma separated) blank to skip', '')
                if ans:
                    cons['enum'] = [v.strip() for v in ans.split(',') if v.strip()]
            changed = True
    if changed:
        p.write_text(yaml.safe_dump(y, sort_keys=False, allow_unicode=True), encoding='utf-8')
        print('[enrich] constraints updated:', db_yaml_path)
    else:
        print('[enrich] nothing to update')
    return 0

if __name__ == '__main__':
    sys.exit(enrich_db_constraints())
""")

# ---------------------------------------------------------------------
# 2) Default RBAC policy (non-destructive if exists)
# ---------------------------------------------------------------------
W('policy/rbac.yaml', r"""
roles: [admin, manager, user]
entities:
  default:
    visible:   [admin, manager, user]
    editable:  [admin, manager]
  # example overrides per entity/field:
  # items:
  #   fields:
  #     description: { visible: [admin, manager], editable: [admin] }
""", overwrite=False)

# ---------------------------------------------------------------------
# 3) Form Generator (Zod + RHF + RBAC‑aware)
# ---------------------------------------------------------------------
W('builder_v2/formgen.py', r"""
from __future__ import annotations
from pathlib import Path
import yaml, json, re

WEB = Path('web/next')
PAGES = WEB/'pages'
COMP = WEB/'components'
LIB  = WEB/'lib'
SCHEMAS = WEB/'schemas'

Z_IMPORT = "import { z } from 'zod'\n"
Z_RESOLVER = "import { zodResolver } from '@hookform/resolvers/zod'\n"
RHF_IMPORT = "import { useForm } from 'react-hook-form'\n"
RBAC_IMPORT = "import { useRole, canEdit, canView } from '../lib/rbac'\n"

FIELD_COMP = ""
import React from 'react'
export function Field({label, name, register, errors, disabled}:{label:string;name:string;register:any;errors:any;disabled?:boolean}){
  return <div style={{marginBottom:12, opacity: disabled?0.6:1}}>
    <label style={{display:'block',fontWeight:600}}>{label}</label>
    <input {...register(name)} disabled={disabled} style={{padding:8,border:'1px solid #ddd',borderRadius:8,width:'100%'}} />
    {errors?.[name] && <div style={{color:'crimson',fontSize:12}}>{String(errors[name].message||'שדה לא תקין')}</div>}
  </div>
}
""

RBAC_TS = ""
let _role = 'admin' as 'admin'|'manager'|'user'
export function setRole(r:'admin'|'manager'|'user'){ _role = r }
export function useRole(){ return _role }
export function canView(role:string, entity:string, field?:string, rbac:any){
  const e = rbac.entities?.[entity] || {}
  const f = e.fields?.[field||''] || {}
  const allow = (f.visible || e.visible || rbac.entities?.default?.visible || [])
  return allow.includes(role)
}
export function canEdit(role:string, entity:string, field?:string, rbac:any){
  const e = rbac.entities?.[entity] || {}
  const f = e.fields?.[field||''] || {}
  const allow = (f.editable || e.editable || rbac.entities?.default?.editable || [])
  return allow.includes(role)
}
""

APP_APPEND = ""
// RBAC RoleProvider: choose role via query (?role=user)
import { useEffect } from 'react'
import { setRole } from '../lib/rbac'
export default function AppWrapper({ Component, pageProps }: any){
  useEffect(()=>{ const p = new URLSearchParams(window.location.search); const r=p.get('role'); if(r) setRole(r as any) },[])
  return <Component {...pageProps} />
}
""

FORM_TS = ""
{z_import}{z_resolver}{rhf_import}{rbac_import}
import { Field } from '../components/Field'
import rbac from '../../policy/rbac.json'

export default function {Cls}Form(){{
  const role = useRole()
  const Schema = {schema}
  type FormT = z.infer<typeof Schema>
  const {{ register, handleSubmit, reset, formState: {{ errors }} }} = useForm<FormT>({{ resolver: zodResolver(Schema) }})
  const onSubmit = async (data:FormT)=>{{
    const res = await fetch('/api/{route}', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(data) }})
    if(res.ok) reset()
  }}
  return <main style={{maxWidth:640, margin:'40px auto', fontFamily:'system-ui'}}>
    <h1 style={{fontSize:24, fontWeight:700, marginBottom:16}}>{Cls} — טופס</h1>
    <form onSubmit={{handleSubmit(onSubmit)}}>
{fields}
      <button type='submit' style={{padding:'10px 16px',borderRadius:8}}>שמור</button>
    </form>
  </main>
}}
""

Z_RULES = {
  'string': lambda c: "z.string()",
  'text':   lambda c: "z.string()",
  'int':    lambda c: "z.number().int()",
  'float':  lambda c: "z.number()",
}


def _z_for(col: dict) -> str:
    t = str(col.get('type','str'))
    base = 'string'
    if 'int' in t: base='int'
    elif 'float' in t or 'num' in t: base='float'
    elif 'text' in t: base='text'
    z = Z_RULES[base](col)
    cons = col.get('constraints',{})
    if cons.get('min') is not None:
        z += f".min({int(cons['min'])})" if base in ('string','text') else f".min({float(cons['min'])})"
    if cons.get('max') is not None:
        z += f".max({int(cons['max'])})" if base in ('string','text') else f".max({float(cons['max'])})"
    if cons.get('regex'):
        z += f".regex(new RegExp('{re.escape(str(cons['regex']))}'))"
    if cons.get('enum'):
        opts = ','.join([f"'{str(v)}'" for v in cons['enum']])
        z = f"z.enum([{opts}])"
    if not cons.get('required', False):
        z += '.optional()'
    return z


def generate_forms(db_yaml: str = 'specs/contracts/db.yaml', rbac_yaml: str = 'policy/rbac.yaml'):
    # load db spec
    db = yaml.safe_load(Path(db_yaml).read_text())
    rbac = yaml.safe_load(Path(rbac_yaml).read_text()) if Path(rbac_yaml).exists() else {'entities':{'default':{'visible':['admin','manager','user'],'editable':['admin','manager']}}}
    # emit rbac.json for frontend
    POL = Path('web/policy'); POL.mkdir(parents=True, exist_ok=True)
    (POL/'rbac.json').write_text(json.dumps(rbac, ensure_ascii=False, indent=2), encoding='utf-8')

    # ensure scaffolds
    PAGES.mkdir(parents=True, exist_ok=True); COMP.mkdir(parents=True, exist_ok=True); LIB.mkdir(parents=True, exist_ok=True); SCHEMAS.mkdir(parents=True, exist_ok=True)
    (COMP/'Field.tsx').write_text(FIELD_COMP, encoding='utf-8')
    (LIB/'rbac.ts').write_text(RBAC_TS, encoding='utf-8')

    # _app wrapper (append if not present)
    app = PAGES/'_app.tsx'
    if not app.exists():
        app.write_text(""import type { AppProps } from 'next/app'\nfunction App({ Component, pageProps }: AppProps){ return <Component {...pageProps} /> }\nexport default App\n"", encoding='utf-8')
    APP_TXT = app.read_text(encoding='utf-8')
    if 'RoleProvider' not in APP_TXT and 'setRole' not in APP_TXT:
        app.write_text(APP_TXT + "\n" + APP_APPEND, encoding='utf-8')

    for ent in db.get('db', []):
        tbl = ent['table']
        cls = ''.join([p.capitalize() for p in tbl.split('_')])
        fields = []
        schema_fields = []
        for c in ent.get('columns', []):
            name = c['name']
            if c.get('pk'): continue
            schema_fields.append(f"  {name}: {_z_for(c)}")
            # RBAC: hide/disable by role
            vis = f"!canView(role, '{tbl}', '{name}', rbac)"
            ed  = f"!canEdit(role, '{tbl}', '{name}', rbac)"
            fields.append(f"      {{!({vis})}} && <Field label='{name}' name='{name}' register={{register}} errors={{errors}} disabled={{{ {ed} }}} />")
        schema_ts = Z_IMPORT + f"export const {cls}Schema = z.object({{\n" + ",\n".join(schema_fields) + "\n})\nexport type " + cls + "Input = z.infer<typeof " + cls + "Schema>\n"
        (SCHEMAS/(tbl + '.schema.ts')).write_text(schema_ts, encoding='utf-8')
        page_ts = FORM_TS.format(
            z_import=Z_IMPORT,
            z_resolver=Z_RESOLVER,
            rhf_import=RHF_IMPORT,
            rbac_import=RBAC_IMPORT,
            Cls=cls,
            route=tbl,
            schema=f"{cls}Schema",
            fields='\n'.join(fields)
        )
        (PAGES/(tbl + '.tsx')).write_text(page_ts, encoding='utf-8')
    print('[forms] generated Zod schemas and RBAC-aware pages under web/next')

if __name__ == '__main__':
    generate_forms()
""")

# ---------------------------------------------------------------------
# 4) OTEL → KPI: add JSONL exporter & aggregator
# ---------------------------------------------------------------------
W('server/middleware/otel.py', r"""
from __future__ import annotations
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import os, json, pathlib, time

class JsonlSpanExporter(SpanExporter):
    def __init__(self, path: str = '.imu_runs/otel_spans.jsonl'):
        self.p = pathlib.Path(path); self.p.parent.mkdir(parents=True, exist_ok=True)
    def export(self, spans):
        with self.p.open('a', encoding='utf-8') as f:
            for s in spans:
                ctx = s.get_span_context()
                attrs = getattr(s, 'attributes', {}) or {}
                rec = {
                    'ts': time.time(),
                    'trace_id': str(ctx.trace_id),
                    'span_id': str(ctx.span_id),
                    'name': s.name,
                    'status': str(getattr(getattr(s, 'status', None), 'status_code', 'OK')),
                    'start': getattr(s, 'start_time', 0),
                    'end': getattr(s, 'end_time', 0),
                    'attrs': {k:str(v) for k,v in attrs.items()},
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS


def instrument_app(app: FastAPI, service_name: str = 'imu-api') -> None:
    endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317')
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    provider.add_span_processor(BatchSpanProcessor(JsonlSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
""", overwrite=True)

W('services/selfopt/otel_to_kpi.py', r"""
from __future__ import annotations
from pathlib import Path
import json, time

SPANS = Path('.imu_runs/otel_spans.jsonl')
KPIS  = Path('.imu_runs/llm_kpis.jsonl')  # reuse bandit log for simplicity

# naive aggregator: per route/operation compute latency & error ratio

def _iter_jsonl(p: Path):
    if not p.exists():
        return []
    for line in p.read_text(encoding='utf-8').splitlines():
        try:
            yield json.loads(line)
        except Exception:
            continue

def aggregate():
    buckets = {}
    for rec in _iter_jsonl(SPANS):
        name = rec.get('name','op')
        dur  = max(0, (rec.get('end',0) - rec.get('start',0)) / 1e6)
        err  = 1.0 if 'ERROR' in str(rec.get('status','')).upper() else 0.0
        b = buckets.setdefault(name, {'n':0, 'dur':0.0, 'err':0.0})
        b['n'] += 1; b['dur'] += dur; b['err'] += err
    now = time.time()
    out = []
    for name, b in buckets.items():
        avg_lat = (b['dur']/b['n']) if b['n'] else 0.0
        err_rate = (b['err']/b['n']) if b['n'] else 0.0
        out.append({'ts': now, 'op': name, 'avg_latency_ms': avg_lat, 'error_rate': err_rate})
        # write also to bandit log as synthetic KPI (provider/model unknown here)
        with KPIS.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': now, 'provider': 'otel', 'model': name, 'ptok':0,'ctok':0,
                                'cost':0.0, 'latency_ms': avg_lat, 'ok': (err_rate<0.5)}, ensure_ascii=False)+"\n")
    return out

if __name__ == '__main__':
    res = aggregate()
    print(json.dumps({'ops': len(res)}, ensure_ascii=False))
""")

# ---------------------------------------------------------------------
# 5) Makefile targets
# ---------------------------------------------------------------------
W('Makefile', r"""
.PHONY: interview enrich forms otel_kpi

interview:
	@python interview/engine.py || true

enrich:
	@python interview/constraints_enricher.py

forms:
	@python -m builder_v2.formgen

otel_kpi:
	@python services/selfopt/otel_to_kpi.py
""", overwrite=False)

print('[OK] IMU M5 — forms+rbac+otel_kpi+constraint-interview written. Run: python IMU_M5_FORMS_RBAC_OTELKPI.py')
