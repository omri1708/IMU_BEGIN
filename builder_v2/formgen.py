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
