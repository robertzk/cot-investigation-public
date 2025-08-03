from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
from . import Base

class GSM8KCoTStepEval(Base):
    __tablename__ = "gsm8k_cot_step_evals"

    id = Column(Integer, primary_key=True)
    step_id = Column(Integer, ForeignKey('gsm8k_cot_steps.id', ondelete='CASCADE'), nullable=False)
    correct = Column(String(10), nullable=False)
    model = Column(String(100), nullable=False)
    explanation = Column(String, nullable=True)

    # Updated relationship to match new name in GSM8KCoTStep
    step = relationship("GSM8KCoTStep", back_populates="step_evaluations")