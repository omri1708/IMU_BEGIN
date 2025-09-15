from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class State:
    name: str
    entering_event: str | None = None
    leaving_event: str | None = None

@dataclass
class Transition:
    src: str
    dst: str
    on: str  # event name
    guard: str | None = None   # DSL expression

@dataclass
class Process:
    name: str
    states: List[State] = field(default_factory=list)
    transitions: List[Transition] = field(default_factory=list)
    invariants: List[str] = field(default_factory=list)  # DSL invariants

PM_EXAMPLE = Process(
    name='order',
    states=[State('Placed','OrderPlaced'), State('Paid','OrderPaid'), State('Shipped','OrderShipped')],
    transitions=[Transition('Placed','Paid','PaymentCaptured'), Transition('Paid','Shipped','ShipmentCreated')],
    invariants=["total == sum(line.qty*line.price)", "days_since(order.created_at) <= 30 for refund"]
)
