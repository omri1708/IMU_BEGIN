from __future__ import annotations
import yaml
from pathlib import Path
from .ner_pii import NER

POL = Path('policy/pii.yaml')
RBAC = Path('policy/rbac.yaml')

_NER_ENGINE = None
def get_ner():
    global _NER_ENGINE
    if _NER_ENGINE is None:
        try:
            _NER_ENGINE = NER()
        except Exception:
            # fallback: רק רג׳קס, בלי מודל
            class _Dummy:
                def find(self, text): return []
                def mask(self, text, role, policy): return text
            _NER_ENGINE = _Dummy()
    return _NER_ENGINE

MASKS = {
    'partial': lambda v: (v[:2] + '***' + v[-2:]) if isinstance(v,str) and len(v)>=4 else '***',
    'last4':   lambda v: ('**** **** **** ' + v[-4:]) if isinstance(v,str) and len(v)>=4 else '****',
    'coarse':  lambda v: '***',
}

def _load_yaml(p: Path, dflt: dict):
    try: return yaml.safe_load(p.read_text()) if p.exists() else dflt
    except Exception: return dflt


def load_policies():
    pii = _load_yaml(POL, {'classes':{}})
    rbac = _load_yaml(RBAC, {'roles':['admin','manager','user'], 'entities':{'default':{'visible':['admin','manager','user'],'editable':['admin','manager']}}})
    return pii, rbac


def apply_redaction(obj, role: str, pii: dict, rbac: dict):
    ner = get_ner()
    if isinstance(obj, dict):
        out = {}
        for k,v in obj.items():
            # rule: field name implies class (suffix heuristic), else NER on strings
            cls = None
            for c in pii.get('classes',{}).keys():
                if k.lower().endswith(c): cls = c; break
            if isinstance(v, str):
                if cls:
                    allow = role in (pii.get('classes',{}).get(cls,{}).get('roles_allow',[]) or [])
                    out[k] = v if allow else MASKS.get(pii['classes'][cls].get('mask','partial'), MASKS['partial'])(v)
                else:
                    out[k] = ner.mask(v, role, pii)
            else:
                out[k] = apply_redaction(v, role, pii, rbac)
        return out
    if isinstance(obj, list):
        return [apply_redaction(x, role, pii, rbac) for x in obj]
    return obj
