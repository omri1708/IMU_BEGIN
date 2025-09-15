from __future__ import annotations
import json, subprocess, shutil
from pathlib import Path

POL=Path('policy/opa')

class OPA:
    def __init__(self):
        self.has_opa = bool(shutil.which('opa'))

    def query(self, pkg: str, rule: str, data: dict) -> dict:
        if self.has_opa:
            q = f"data.{pkg}.{rule}"
            p = subprocess.run(['opa','eval','-I','-d',str(POL), q], input=json.dumps(data), text=True, capture_output=True)
            if p.returncode==0:
                try:
                    out=json.loads(p.stdout)
                    return out
                except Exception:
                    return {'result': None}
        # fallback: naive rules
        if pkg=='policy.abac' and rule=='allow':
            role=data.get('request',{}).get('user',{}).get('role')
            action=data.get('request',{}).get('action')
            if role=='admin': return {'result':True}
            if role=='manager' and action=='read': return {'result':True}
            return {'result':False}
        if pkg=='policy.consent' and rule=='granted':
            res=data.get('resource',{})
            if not res.get('sensitive'): return {'result':True}
            cons=data.get('request',{}).get('user',{}).get('consent',{})
            return {'result': bool(cons.get(res.get('purpose')))}
        if pkg=='policy.retention' and rule=='within':
            res=data.get('resource',{})
            if not res.get('retention_days'): return {'result':True}
            import time
            now=time.time(); created=res.get('created_at', now); limit=res.get('retention_days',0)*24*3600
            return {'result': (now-created)<=limit}
        return {'result': None}
