from __future__ import annotations
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, UniqueConstraint
Base = declarative_base()

class IdempotencyKey(Base):
    __tablename__ = 'idempotency'
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True)
    endpoint = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('key','endpoint', name='uq_key_ep'),)
