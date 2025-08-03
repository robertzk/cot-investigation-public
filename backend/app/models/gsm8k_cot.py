from sqlalchemy import Column, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from . import Base

class GSM8KCoT(Base):
    __tablename__ = "gsm8k_cot"

    id = Column(Integer, primary_key=True)
    gsm8k_id = Column(Integer, ForeignKey('gsm8k.id'), nullable=False)
    language_model_id = Column(Integer, ForeignKey('language_models.id'), nullable=False)
    params = Column(JSON, nullable=False)
    raw_response = Column(Text, nullable=False)

    # Relationships
    # gsm8k_question = relationship("GSM8K", back_populates="chains_of_thought")
    # language_model = relationship("LanguageModel", back_populates="gsm8k_responses")
    cot_steps = relationship("GSM8KCoTStep", back_populates="cot", cascade="all, delete-orphan")