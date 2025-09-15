from __future__ import annotations
import re
# Tiny DSL parser for expressions like: field: type! [min=, max=, regex=, enum=]

def parse_field(spec: str):
    # e.g., 'email: str! regex=^.+@.+$'
    name, rest = [x.strip() for x in spec.split(':',1)]
    parts = rest.split()
    type_req = parts[0]
    base = type_req.rstrip('!')
    req  = type_req.endswith('!')
    cons = {}
    for p in parts[1:]:
        if '=' in p:
            k,v = p.split('=',1); cons[k]=v
    return name, base, req, cons
