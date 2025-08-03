from functools import cached_property
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from typing import Dict, Any
from sqlalchemy.orm import relationship
from app.models import Base
from app.data_structures.cot_trie import CotTrie as CotTrieDS

class CotTrie(Base):
    __tablename__ = 'cot_tries'

    id = Column(Integer, primary_key=True)
    dataset = Column(String(50), nullable=False, server_default='gsm8k')
    problem_id = Column(Integer, ForeignKey('problems.id'), nullable=False)
    model = Column(String(100), nullable=False)
    trie = Column(JSON, nullable=False)
    trie_evaled = Column(JSONB, nullable=True)
    trie_evaled_alt1 = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), 
                       server_default=func.now(),
                       onupdate=func.now(),
                       nullable=False)

    problem = relationship("Problem", back_populates="cot_tries")
    cot_paths = relationship("CotPath", back_populates="cot_trie") 

    __table_args__ = (
        # Index for faster lookups
        Index('ix_cot_tries_dataset_problem_id', 'dataset', 'problem_id'),
        Index('ix_cot_tries_trie_evaled', 'trie_evaled', postgresql_using='gin'),
        Index('ix_cot_tries_trie_evaled_alt1', 'trie_evaled_alt1', postgresql_using='gin'),
        # Unique constraint to prevent duplicates
        UniqueConstraint('dataset', 'problem_id', 'model', 
                           name='uq_cot_tries_dataset_problem_model'),
    )

    @cached_property
    def cot_trie_ds(self) -> CotTrieDS:
        return CotTrieDS(self.trie)

    def __repr__(self):
        return f"<CotTrie(id={self.id}, dataset='{self.dataset}', problem_id={self.problem_id}, model='{self.model}')>" 