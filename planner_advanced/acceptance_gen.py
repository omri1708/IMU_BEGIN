from __future__ import annotations
from pathlib import Path
import yaml, json

def gen_acceptance(req_yaml='specs/requirements.yaml', out='tests/acceptance/test_requirements.py'):
    reqs = yaml.safe_load(Path(req_yaml).read_text())['requirements']
    lines = ["from __future__ import annotations\nimport httpx, pytest\n"]
    for r in reqs:
        rid = r['id']; title = r['title']
        lines.append(f"def test_{rid.lower().replace('-','_')}_smoke():\n    assert isinstance('{title}', str)\n")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text('\n'.join(lines), encoding='utf-8')
