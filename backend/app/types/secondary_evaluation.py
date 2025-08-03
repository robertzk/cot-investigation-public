from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Any

class ProblemCode(Enum):
    INCORRECT = "incorrect"
    UNUSED = "unused"
    UNFAITHFUL = "unfaithful"
    NONE = "none"

class SeverityCode(Enum):
    TRIVIAL = "trivial"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class StepEvaluationCheck:
    """A check of an evaluation of a single step in a reasoning chain."""
    status: ProblemCode
    severity: SeverityCode
    explanation: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            'status': self.status.value,
            'severity': self.severity.value,
            'explanation': self.explanation
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional['StepEvaluationCheck']:
        """Create from a dictionary."""
        if not data:
            return None
        return cls(
            status=ProblemCode(data['status']),
            severity=SeverityCode(data['severity']),
            explanation=data['explanation']
        )

@dataclass
class StepEvaluation:
    """Evaluation of a single step in a reasoning chain."""
    status: ProblemCode
    severity: SeverityCode
    explanation: Optional[str] = None
    original_check: Optional[StepEvaluationCheck] = None
    second_check: Optional[StepEvaluationCheck] = None

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            'status': self.status.value,
            'severity': self.severity.value,
            'explanation': self.explanation,
            'original_check': self.original_check.to_dict() if self.original_check else None,
            'second_check': self.second_check.to_dict() if self.second_check else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StepEvaluation':
        """Create from a dictionary."""
        return cls(
            status=ProblemCode(data['status']),
            severity=SeverityCode(data['severity']),
            explanation=data['explanation'],
            original_check=StepEvaluationCheck.from_dict(data.get('original_check')),
            second_check=StepEvaluationCheck.from_dict(data.get('second_check'))
        )

@dataclass
class PathEvaluation:
    """Full evaluation of a reasoning chain."""
    reasoning: Optional[str]
    step_evaluations: Dict[int, StepEvaluation]

@dataclass
class CotTrieNodeSecondaryEvaluations:
    """Collection of evaluations for a node from different paths."""
    evaluations: List[StepEvaluation] = None
    reasoning: Optional[str] = None

    def __init__(self):
        self.evaluations = []

    def add_evaluation(self, eval_: StepEvaluation):
        self.evaluations.append(eval_)
    
    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        result = {'evaluations': [eval_.to_dict() for eval_ in self.evaluations]}
        if self.reasoning is not None:
            result['reasoning'] = self.reasoning
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CotTrieNodeSecondaryEvaluations':
        """Create from a dictionary."""
        instance = cls()
        instance.evaluations = [StepEvaluation.from_dict(eval_data) 
                              for eval_data in data['evaluations']]
        instance.reasoning = data.get('reasoning')
        return instance 
