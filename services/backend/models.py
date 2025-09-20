from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, func

Base = declarative_base()
class Items(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text)

    __table_args__ = (

    )
class Outbox(Base):
    __tablename__ = "outbox"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    topic      = Column(String, nullable=False)          
    key        = Column(String, nullable=True)
    action     = Column(String, nullable=False)
    status     = Column(String, nullable=False, default="pending")
    item_id    = Column(Integer, nullable=True)
    payload    = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    sent_at    = Column(DateTime, nullable=True)