from __future__ import annotations
from confluent_kafka import Consumer
import json, sqlite3

class DedupeStore:
    def __init__(self, path='.imu_runs/dedupe.db'):
        self.db = sqlite3.connect(path); self.db.execute('CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY)'); self.db.commit()
    def seen(self, mid: str) -> bool:
        try:
            self.db.execute('INSERT INTO seen(id) VALUES (?)', (mid,)); self.db.commit(); return False
        except Exception:
            return True

class ExactlyOnceConsumer:
    def __init__(self, brokers='localhost:9092', group='imu-ex1', store: DedupeStore | None=None):
        self.c = Consumer({'bootstrap.servers': brokers, 'group.id': group, 'enable.auto.commit': False})
        self.store = store or DedupeStore()
    def run(self, topics, handler):
        self.c.subscribe(topics)
        while True:
            msg = self.c.poll(1.0)
            if not msg: continue
            mid = f"{msg.topic()}:{msg.partition()}:{msg.offset()}"
            if self.store.seen(mid):
                self.c.commit(msg); continue
            handler(json.loads(msg.value().decode('utf-8')))
            self.c.commit(msg)
