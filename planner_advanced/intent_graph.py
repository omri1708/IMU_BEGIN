from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class IntentNode:
    id: str
    text: str
    kind: str  # user_goal | implicit_req | nonfunc | policy
    children: List[str] = field(default_factory=list)

@dataclass
class ContextSpec:
    name: str
    domain: str
    capabilities: List[str]
    events_in: List[str] = field(default_factory=list)
    events_out: List[str] = field(default_factory=list)

@dataclass
class PlanSpec:
    intents: List[IntentNode]
    contexts: List[ContextSpec]
    arch_style: str
    nonfunc: Dict[str, Any]
    contracts: Dict[str, Any]

