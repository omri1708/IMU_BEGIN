from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, func
from sqlalchemy import DateTime

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
    id          = Column(Integer, primary_key=True, autoincrement=True)
    topic       = Column(String, nullable=False)        # "items"
    key         = Column(String, nullable=True)         # item_id
    action      = Column(String, nullable=False)        # "deleted"
    payload     = Column(Text, nullable=False)          # JSON
    status      = Column(String, nullable=False, default="pending")
    created_at  = Column(DateTime, server_default=func.now())