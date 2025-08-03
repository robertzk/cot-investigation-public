from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship
from app.models import Base

class GSM8K(Base):
    __tablename__ = "gsm8k"

    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    # chains_of_thought = relationship("GSM8KCoT", back_populates="gsm8k_question")
    cot_tries = relationship(
        "CotTrie",
        primaryjoin="GSM8K.id == CotTrie.problem_id",
        back_populates="problem"
    )