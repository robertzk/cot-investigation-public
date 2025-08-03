from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from . import Base

class LanguageModel(Base):
    __tablename__ = "language_models"

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False, unique=True)
    model_provider = Column(String(50), nullable=False)

    # Add the relationship to GSM8KCoT
    #gsm8k_responses = relationship("GSM8KCoT", back_populates="language_model")
 