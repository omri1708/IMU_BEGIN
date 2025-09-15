from __future__ import annotations
from typing import Dict, Any, List

def gen_openapi(service: str, apis: List[Dict[str,Any]]) -> Dict[str, Any]:
    paths = {}
    for a in apis:
        m = a.get('method','get').lower()
        p = a.get('path','/')
        paths.setdefault(p, {})[m] = {'responses': {'200': {'description': 'OK'}}}
    return {'openapi': '3.1.0', 'info': {'title': service, 'version':'1.0.0'}, 'paths': paths}
