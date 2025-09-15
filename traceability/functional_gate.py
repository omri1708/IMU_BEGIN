from __future__ import annotations
from pathlib import Path
import yaml, json

def main():
    req = yaml.safe_load(Path('specs/requirements.yaml').read_text())['requirements']
    api = yaml.safe_load(Path('specs/contracts/api.yaml').read_text())['api']
    db  = yaml.safe_load(Path('specs/contracts/db.yaml').read_text())['db']
    ui  = yaml.safe_load(Path('specs/contracts/ui.yaml').read_text())['ui']
    # functional hint: each REQ must map to at least one API + one DB + one UI artifact
    cov = {}
    missing = []
    for r in req:
        rid = r['id']; cov[rid] = {'api':0,'db':0,'ui':0}
        for a in api:
            if rid in (a.get('req') or []): cov[rid]['api'] += 1
        for d in db:
            if rid in (d.get('req') or []): cov[rid]['db'] += 1
        for u in ui:
            if rid in (u.get('req') or []): cov[rid]['ui'] += 1
        if min(cov[rid].values()) == 0:
            missing.append(rid)
    print(json.dumps({'coverage': cov, 'missing': missing}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if missing else 0)

if __name__=='__main__':
    main()
