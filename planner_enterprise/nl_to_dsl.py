from __future__ import annotations
# Heuristic bridge: turn interview flows/personas into a starter DSL

def seed_dsl(use_case: str, flows: list[str]) -> str:
    ents = ["entity Customer { id: uuid; email: str; name: str; }"]
    pro = ["process order { state Placed; state Paid; state Shipped;\n  transition Placed -> Paid on PaymentCaptured;\n  transition Paid -> Shipped on ShipmentCreated;\n  invariant total == sum(line.qty*line.price); }"]
    return "\n\n".join(ents + pro)
