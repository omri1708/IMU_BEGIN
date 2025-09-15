from __future__ import annotations
from z3 import Real, Solver, And, sat

# example: refund amount <= order.total and within window handled in OPA; here numeric check

def check_refund(amount: float, order_total: float) -> bool:
    a = Real('a'); t = Real('t')
    s = Solver(); s.add(a == amount, t == order_total)
    s.add(a <= t)
    return s.check() == sat
