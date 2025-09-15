from __future__ import annotations
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base
Base = declarative_base()

class Outbox(Base):
    __tablename__ = 'outbox'
    id = Column(Integer, primary_key=True)
    topic = Column(String)
    payload = Column(Text)
    status = Column(String, default='pending')
