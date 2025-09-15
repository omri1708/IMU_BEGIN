from __future__ import annotations
import random

def route(percent: int = 10) -> bool:
    return random.randint(1,100) <= percent
