from typing import Callable, Union, Dict, Any, List
from sqlalchemy import Column, Integer, Boolean, JSON, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from dataclasses import asdict

from app.models.cot_trie import CotTrie
from app.models.experiment import CotTrieEvalExperimentRecord
from app.data_structures.cot_path import CotPath as CotPathDS
from app.types.correctness import Correctness
from app.types.cot_trie import CotTrieNode

from . import Base

class CotPath(Base):
    __tablename__ = 'cot_path'

    id = Column(Integer, primary_key=True)
    cot_trie_id = Column(Integer, ForeignKey('cot_tries.id'))
    cot_trie_eval_experiment_record_id = Column(
        Integer, 
        ForeignKey('cot_trie_eval_experiment_record.id')
    )
    node_ids = Column(JSON, nullable=False)
    cot_path = Column(JSON, nullable=False)
    answer_correct = Column(Boolean)
    is_unfaithful = Column(Boolean)

    # Relationships
    cot_trie = relationship("CotTrie", back_populates="cot_paths")
    experiment_record = relationship(
        "CotTrieEvalExperimentRecord", 
        back_populates="paths"
    )

    __table_args__ = (
        CheckConstraint(
            '(cot_trie_id IS NULL AND cot_trie_eval_experiment_record_id IS NOT NULL) OR '
            '(cot_trie_id IS NOT NULL AND cot_trie_eval_experiment_record_id IS NULL)',
            name='exactly_one_reference_check'
        ),
    )

    def cot_object(self) -> Union[CotTrie, CotTrieEvalExperimentRecord]:
        if self.cot_trie_id:
            return self.cot_trie
        else:
            return self.experiment_record.cot_trie
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_ids": self.node_ids,
            "cot_path": self.cot_path,
            "answer_correct": self.answer_correct,
            "is_unfaithful": self.is_unfaithful
        }

    @staticmethod
    def from_cot_path(
        path: CotPathDS, 
        *,
        cot_trie_id: int = None,
        experiment_record_id: int = None,
        unfaithfulness_condition: Callable[[CotTrieNode], bool] = None
    ) -> 'CotPath':
        """Create a CotPath record from a CotPath data structure."""
        # Validate that exactly one ID is provided
        if not bool(cot_trie_id) ^ bool(experiment_record_id):
            raise ValueError("Must provide exactly one of cot_trie_id or experiment_record_id")
        
        if unfaithfulness_condition is None:
            unfaithfulness_condition = lambda node: node.content.secondary_eval and \
                any(eval_.status.value == 'unfaithful' and eval_.severity.value in ('minor', 'major', 'critical') for eval_ in node.content.secondary_eval.evaluations)  # noqa: E731

        # Get last node to check answer correctness
        last_node = path.nodes[-1]
        answer_correct = (
            last_node.content.answer_correct and 
            last_node.content.answer_correct.correct == Correctness.CORRECT
        )

        # Check for unfaithful steps
        has_unfaithful = any(
            unfaithfulness_condition(node)
            for node in path.nodes
        )

        # Get node IDs
        node_ids = [
            node.node_id for node in path.nodes
            if node.node_id is not None
        ]

        # Serialize path
        serialized_path = [
            node.serialize(children=False) for node in path.nodes
        ]

        return CotPath(
            cot_trie_id=cot_trie_id,
            cot_trie_eval_experiment_record_id=experiment_record_id,
            node_ids=node_ids,
            cot_path=serialized_path,
            answer_correct=answer_correct,
            is_unfaithful=has_unfaithful
        )
