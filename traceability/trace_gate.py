from pathlib import Path
import json, yaml, sys

req = yaml.safe_load(Path("specs/requirements.yaml").read_text())['requirements']
api = yaml.safe_load(Path("specs/contracts/api.yaml").read_text())['api']
db  = yaml.safe_load(Path("specs/contracts/db.yaml").read_text())['db']
ui  = yaml.safe_load(Path("specs/contracts/ui.yaml").read_text())['ui']

rq = {r['id']: {"api": 0, "db": 0, "ui": 0} for r in req}
for a in api:
    for rid in a.get('req', []):
        if rid in rq: rq[rid]['api'] += 1
for d in db:
    for rid in d.get('req', []):
        if rid in rq: rq[rid]['db'] += 1
for u in ui:
    for rid in u.get('req', []):
        if rid in rq: rq[rid]['ui'] += 1

missing = [rid for rid, v in rq.items() if max(v.values()) == 0]
print(json.dumps({"coverage": rq, "missing": missing}, ensure_ascii=False, indent=2))
sys.exit(1 if missing else 0)
