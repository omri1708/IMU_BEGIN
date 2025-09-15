from __future__ import annotations
from typing import Dict, Any, List
import re
from .process_model import Process, State, Transition

# Heuristic multi-stage extractor (regex + cue phrases) → processes & events

CUES_EVT = {
  'pay': ['pay','payment','capture','checkout','charge'],
  'ship': ['ship','shipment','dispatch','delivery'],
  'refund': ['refund','chargeback','return']
}

def infer_processes(nl: str) -> List[Process]:
    t = nl.lower()
    states = [State('Placed','OrderPlaced')]
    trans = []
    if any(c in t for c in CUES_EVT['pay']):
        states.append(State('Paid','OrderPaid'))
        trans.append(Transition('Placed','Paid','PaymentCaptured'))
    if any(c in t for c in CUES_EVT['ship']):
        states.append(State('Shipped','OrderShipped'))
        trans.append(Transition('Paid','Shipped','ShipmentCreated'))
    inv = ["total == sum(line.qty*line.price)"]
    if any(c in t for c in CUES_EVT['refund']):
        inv.append("days_since(order.created_at) <= 30 for refund")
    return [Process('order', states, trans, inv)]
