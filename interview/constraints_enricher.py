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
