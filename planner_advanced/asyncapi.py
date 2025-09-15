from __future__ import annotations
from typing import Dict, Any, List

def gen_asyncapi(service: str, events_in: List[str], events_out: List[str]) -> Dict[str, Any]:
    return {
      'asyncapi': '2.6.0', 'info': {'title': f'{service} Events', 'version':'1.0.0'},
      'channels': { **{f'{e}.in': {'subscribe': {'message': {'name': e}}} for e in events_in},
                    **{f'{e}.out':{'publish':   {'message': {'name': e}}} for e in events_out} }
    }
