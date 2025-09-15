from __future__ import annotations
from confluent_kafka import Producer, Consumer, KafkaException
import json, time

class TxProducer:
    def __init__(self, brokers='localhost:9092', transactional_id='imu-tx-1'):
        self.p = Producer({'bootstrap.servers': brokers, 'enable.idempotence': True,
                           'transactional.id': transactional_id, 'acks': 'all'})
        self.p.init_transactions()
    def send(self, topic: str, key: str, value: dict):
        try:
            self.p.begin_transaction()
            self.p.produce(topic, key=key, value=json.dumps(value).encode('utf-8'))
            self.p.commit_transaction()
        except KafkaException:
            self.p.abort_transaction(); raise

class TxConsumer:
    def __init__(self, brokers='localhost:9092', group='imu-cg-1'):
        self.c = Consumer({'bootstrap.servers': brokers, 'group.id': group, 'enable.auto.commit': False,
                           'isolation.level': 'read_committed'})
    def subscribe(self, topics): self.c.subscribe(topics)
    def poll(self, timeout=1.0): return self.c.poll(timeout)
    def commit(self, msg): self.c.commit(msg)
