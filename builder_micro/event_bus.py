from __future__ import annotations
from typing import Dict, Any
import os

class EventBus:
    def __init__(self):
        self.backend = os.getenv('IMU_BUS','redis')
    def publish(self, topic: str, msg: Dict[str,Any]):
        # placeholder: plug Kafka/Redis here
        pass
    def subscribe(self, topic: str):
        yield from ()
