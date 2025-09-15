from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List

@dataclass
class Step:
    do: Callable
    undo: Callable

def run_saga(steps: List[Step]):
    done = []
    try:
        for s in steps:
            s.do(); done.append(s)
    except Exception:
        for s in reversed(done):
            try: s.undo()
            except Exception: pass
        raise
