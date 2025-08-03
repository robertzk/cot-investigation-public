from dataclasses import dataclass, field
from copy import deepcopy
from typing import List, Dict, Any, Optional

from app.types.correctness import Correctness, CorrectnessEvaluation
from app.types.secondary_evaluation import (
    ProblemCode, SeverityCode, StepEvaluationCheck, StepEvaluation,
    CotTrieNodeSecondaryEvaluations
)

@dataclass
class SecondaryEvalStatus:
    status: str
    explanation: str
    severity: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "explanation": self.explanation,
            "severity": self.severity
        }

@dataclass
class SecondaryEval:
    evaluations: List[SecondaryEvalStatus]
    reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reasoning": self.reasoning,
            "evaluations": [eval.to_dict() for eval in self.evaluations]
        }

@dataclass
class CotContent:
    """A class that represents the content of a COT."""
    steps: List[str]
    correct: Correctness
    step_indices: Optional[List[int]] = None
    explanation: Optional[str] = None
    answer_correct: Optional[CorrectnessEvaluation] = None
    args: Optional[List[Dict[str, Any]]] = None
    secondary_eval: Optional[SecondaryEval] = None
    meta: Optional[Dict[str, Any]] = None

@dataclass
class CotTrieNode:
    """A node in a Chain of Thought trie."""
    content: CotContent
    children: List["CotTrieNode"]
    prefix: str = ""
    terminal: bool = False
    node_id: Optional[int] = None

    @classmethod
    def deserialize(cls, node_dict: Dict[str, Any]) -> "CotTrieNode":
        """Create a CotTrieNode from a serialized dictionary."""
        content = node_dict["content"]
        
        # Deserialize answer correctness if present
        answer_correct = None
        if content.get("answer_correct"):
            answer_correct = CorrectnessEvaluation(
                correct=Correctness(content["answer_correct"]["correct"]),
                explanation=content["answer_correct"]["explanation"]
            )
        
        # Deserialize secondary evaluations if present
        secondary_eval = None
        if content.get("secondary_eval"):
            secondary_eval = SecondaryEval(
                evaluations=[
                    StepEvaluation(
                        status=ProblemCode(eval_.get("status")),
                        severity=SeverityCode(eval_.get("severity")),
                        explanation=eval_.get("explanation"),
                        original_check=StepEvaluationCheck.from_dict(eval_.get("original_check")),
                        second_check=StepEvaluationCheck.from_dict(eval_.get("second_check"))
                    )
                    for eval_ in content["secondary_eval"].get("evaluations", [])
                ],
                reasoning=content["secondary_eval"].get("reasoning")
            )
        
        # Create content with optional fields
        content_obj = CotContent(
            steps=content["steps"],
            correct=Correctness(content["correct"]),
            answer_correct=answer_correct,
            secondary_eval=secondary_eval
        )
        if content.get("step_indices"):
            content_obj.step_indices = content["step_indices"]
        if content.get("explanation"):
            content_obj.explanation = content["explanation"]
        if content.get("args"):
            content_obj.args = content["args"]
        if content.get("meta"):
            content_obj.meta = content["meta"]
        
        # Recursively deserialize children
        children = [
            cls.deserialize(child) 
            for child in node_dict.get("children", [])
        ]
        
        return cls(
            content=content_obj,
            children=children,
            prefix=node_dict.get("prefix", ""),
            terminal=node_dict.get("terminal", False),
            node_id=node_dict.get("node_id")
        )

    def __str__(self) -> str:
        return CotTrieVisualizer.visualize(self)
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __hash__(self) -> int:
        """
        For use in dictionaries, as in CotTrie.find_incorrect_paths().
        """
        return hash(id(self))

    def serialize(self, children: bool = True) -> Dict[str, Any]:
        content = {
            "steps": self.content.steps,
            "step_indices": self.content.step_indices,
            "args": self.content.args,
            "correct": self.content.correct.value,
            "answer_correct": {
                "correct": self.content.answer_correct.correct.value,
                "explanation": self.content.answer_correct.explanation
            } if self.content.answer_correct else None,
        }

        if self.content.args:
            content["args"] = self.content.args
        
        if self.content.explanation:
            content["explanation"] = self.content.explanation

        if self.content.meta:
            content["meta"] = self.content.meta
        
        if self.content.secondary_eval:
            content["secondary_eval"] = {
                "evaluations": [
                    {
                        "status": eval_.status.value,
                        "severity": eval_.severity.value,
                        "explanation": eval_.explanation,
                        "original_check": eval_.original_check.to_dict() if eval_.original_check else None,
                        "second_check": eval_.second_check.to_dict() if eval_.second_check else None
                    }
                    for eval_ in self.content.secondary_eval.evaluations
                ],
                "reasoning": self.content.secondary_eval.reasoning
            } if self.content.secondary_eval else None
 
        return {
            "content": content,
            "children": [child.serialize() for child in self.children] if children else [],
            "terminal": self.terminal,
            "prefix": self.prefix,
            "node_id": self.node_id
        }

class CotTrieVisualizer:
    """A class to visualize CotTrie objects in a hierarchical text format."""
    
    @staticmethod
    def visualize(trie_node: CotTrieNode) -> str:
        """Create a string visualization of the trie using in-order traversal."""
        def _visualize_node(node: CotTrieNode, depth: int = 0) -> str:
            indent = "    " * depth
            result = []
            
            for step in node.content.steps:
                result.append(f"{indent}[{step}]")
            
            result.append(f"{indent}status: {node.content.correct.value}")
            if node.terminal:
                result.append(f"{indent}(terminal)")
            
            result.append("")
            
            for child in node.children:
                result.append(_visualize_node(child, depth + 1))
            
            return "\n".join(result)
        
        return _visualize_node(trie_node)
    
    @staticmethod
    def print_trie(trie_node: CotTrieNode):
        """Print the visualization of the trie."""
        print(CotTrieVisualizer.visualize(trie_node)) 