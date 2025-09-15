from __future__ import annotations
from lark import Lark, Transformer, v_args
from pathlib import Path

GRAMMAR = Lark(Path('planner_enterprise/grammar.lark').read_text(encoding='utf-8'))

@v_args(inline=True)
class Build(Transformer):
    def __init__(self):
        self.doc = {"entities":{}, "processes":{}, "policies":{}}
    def entity(self, name, *fields):
        self.doc["entities"][str(name)] = {"fields": list(fields)}
    def field(self, n, t, *cons):
        return {"name": str(n), "type": str(t), "constraints": {c[0]: c[1] for c in cons}}
    def constraint(self, *args):
        # not used; handle as generic
        pass
    def process(self, name, *parts):
        st, tr, inv = [], [], []
        for p in parts:
            if p and p.get('_k')=='state': st.append(p)
            elif p and p.get('_k')=='transition': tr.append(p)
            elif p and p.get('_k')=='invariant': inv.append(p['expr'])
        self.doc["processes"][str(name)] = {"states": st, "transitions": tr, "invariants": inv}
    def state(self, name):
        return {"_k":"state", "name": str(name)}
    def transition(self, src, dst, ev, cond=None):
        return {"_k":"transition", "src": str(src), "dst": str(dst), "event": str(ev), "guard": (str(cond) if cond else None)}
    def invariant(self, expr):
        return {"_k":"invariant", "expr": str(expr)}
    def policy(self, name, *rules):
        self.doc["policies"][str(name)] = {"rules": list(rules)}
    def rule(self, name, expr):
        return {"name": str(name), "expr": str(expr)}


def parse(text: str) -> dict:
    tree = GRAMMAR.parse(text)
    b = Build(); b.transform(tree)
    return b.doc
