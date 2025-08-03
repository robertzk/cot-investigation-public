from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.models import Base

class CotTrieEvalExperiment(Base):
    __tablename__ = 'cot_trie_eval_experiment'

    id = Column(Integer, primary_key=True)
    experiment_desc = Column(String, nullable=False)
    results = Column(JSON)
    
    records = relationship("CotTrieEvalExperimentRecord", back_populates="experiment")

class CotTrieEvalExperimentRecord(Base):
    __tablename__ = 'cot_trie_eval_experiment_record'

    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey('cot_trie_eval_experiment.id'), nullable=False)
    problem_id = Column(Integer, ForeignKey('problems.id'), nullable=False)
    cot_trie_id = Column(Integer, ForeignKey('cot_tries.id'), nullable=False)
    model = Column(String)
    trie_evaled = Column(JSON)

    experiment = relationship("CotTrieEvalExperiment", back_populates="records")
    problem = relationship("Problem")
    cot_trie = relationship("CotTrie")
    paths = relationship("CotPath", back_populates="experiment_record") 