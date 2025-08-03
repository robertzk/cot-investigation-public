from sqlalchemy import Column, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from . import Base

class GSM8KCoTStep(Base):
    __tablename__ = "gsm8k_cot_steps"

    id = Column(Integer, primary_key=True)
    gsm8k_cot_id = Column(Integer, ForeignKey('gsm8k_cot.id'), nullable=False)
    step_number = Column(Integer, nullable=False)
    step_text = Column(Text, nullable=False)

    # Relationship back to the parent CoT
    cot = relationship("GSM8KCoT", back_populates="cot_steps")
    step_evaluations = relationship("GSM8KCoTStepEval", back_populates="step", cascade="all, delete-orphan")

    # Ensure step numbers are unique per CoT entry
    __table_args__ = (
        UniqueConstraint('gsm8k_cot_id', 'step_number', name='uix_cot_step_number'),
    ) 