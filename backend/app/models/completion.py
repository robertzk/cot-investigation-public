from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from . import Base

class Completion(Base):
    __tablename__ = "completions"

    id = Column(Integer, primary_key=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 