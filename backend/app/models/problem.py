from sqlalchemy import Column, Integer, Text, String, JSON
from sqlalchemy.orm import relationship
from app.models import Base

class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True)
    dataset_name = Column(String(50), nullable=False, index=True)
    category = Column(String(100), nullable=True)  # For datasets with subcategories
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    problem_metadata = Column(JSON, nullable=True)  # For additional dataset-specific fields

    # Relationships
    cot_tries = relationship(
        "CotTrie",
        primaryjoin="Problem.id == CotTrie.problem_id",
        back_populates="problem"
    ) 