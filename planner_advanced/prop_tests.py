from __future__ import annotations
from pathlib import Path
import yaml

def gen_property_tests(db_yaml='specs/contracts/db.yaml', out='tests/property/test_properties.py'):
    y = yaml.safe_load(Path(db_yaml).read_text())
    lines = ["from __future__ import annotations\nimport pytest\n"]
    for ent in y.get('db', []):
        tbl = ent['table']
        for c in ent.get('columns', []):
            cons = c.get('constraints', {})
            if cons.get('min') is not None and cons.get('max') is not None:
                lines.append(f"def test_{tbl}_{c['name']}_min_le_max():\n    assert {float(cons['min'])} <= {float(cons['max'])}\n")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text('\n'.join(lines), encoding='utf-8')
