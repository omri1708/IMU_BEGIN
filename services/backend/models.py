from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, CheckConstraint, UniqueConstraint
Base = declarative_base()
class Entities(Base):
    __tablename__ = 'entities'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text)

    __table_args__ = (

    )
