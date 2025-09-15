from __future__ import annotations
from pathlib import Path
import xml.etree.ElementTree as ET
import json, time

J = Path('.imu_runs/test_reports.jsonl')


def parse_junit(xml_path: str | Path):
    p = Path(xml_path)
    tree = ET.parse(p); root = tree.getroot()
    total = int(root.attrib.get('tests','0')); failed = int(root.attrib.get('failures','0')) + int(root.attrib.get('errors','0'))
    cases = []
    for tc in root.iter('testcase'):
        name = tc.attrib.get('name'); cls = tc.attrib.get('classname'); dur = float(tc.attrib.get('time','0'))
        status = 'ok'
        detail = None
        for f in list(tc):
            if f.tag in ('failure','error'):
                status = f.tag; detail = f.attrib.get('message') or (f.text or '').strip()
        cases.append({'name': name, 'class': cls, 'time': dur, 'status': status, 'detail': detail})
    return {'total': total, 'failed': failed, 'cases': cases}


def mine(xml_path: str | Path):
    rep = parse_junit(xml_path)
    rec = {'ts': time.time(), 'summary': {'total': rep['total'], 'failed': rep['failed']},
           'failures': [c for c in rep['cases'] if c['status']!='ok']}
    J.parent.mkdir(parents=True, exist_ok=True)
    with J.open('a', encoding='utf-8') as f: f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    # simple deploy guard
    if rec['summary']['failed'] > 0:
        print(json.dumps({'deploy_guard':'fail','reason':'tests_failed','summary':rec['summary']}, ensure_ascii=False))
        raise SystemExit(2)
    else:
        print(json.dumps({'deploy_guard':'pass','summary':rec['summary']}, ensure_ascii=False))

if __name__ == '__main__':
    import sys
    xml = sys.argv[1] if len(sys.argv)>1 else '.imu_runs/junit.xml'
    mine(xml)
