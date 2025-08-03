from typing import Dict, Any, List, Callable

from app.types.correctness import Correctness, CorrectnessEvaluation
from app.types.cot_trie import CotContent, CotTrieNode, SecondaryEval, SecondaryEvalStatus
from app.data_structures.cot_path import CotPath, NodeVisitStatus
from app.types.secondary_evaluation import SeverityCode, ProblemCode, StepEvaluation, StepEvaluationCheck

class CotTrie:
    """
    A class for deserializing and working with Chain of Thought tries.
    """

    def __init__(self, trie_dict: Dict[str, Any]):
        """
        Initialize a CotTrie from a dictionary representation.
        
        Args:
            trie_dict: Dictionary containing the trie structure
        """
        if trie_dict.get("root") is not None:
            self.root = self._deserialize_node(trie_dict["root"])
        else:
            self.root = None
    
    @classmethod
    def from_root_node(cls, root: CotTrieNode) -> "CotTrie":
        """
        Initialize a CotTrie from a root node.
        """
        return cls({"root": root.serialize()})
    
    @staticmethod
    def _deserialize_node(node_dict: Dict[str, Any]) -> CotTrieNode:
        """
        Recursively deserialize a node and its children from a dictionary.
        
        Args:
            node_dict: Dictionary containing node data
            
        Returns:
            Deserialized CotTrieNode
        """
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
            secondary_eval=secondary_eval,
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
            CotTrie._deserialize_node(child) 
            for child in node_dict["children"]
        ]
        
        return CotTrieNode(
            content=content_obj,
            children=children,
            prefix=node_dict.get("prefix"),
            terminal=node_dict.get("terminal") or len(children) == 0,
            node_id=node_dict.get("node_id")
        )
    
    def size(self) -> int:
        """Get the total number of nodes in the trie."""
        def _size(node: CotTrieNode) -> int:
            return 1 + sum(_size(child) for child in node.children)
        return _size(self.root)
    
    def depth(self) -> int:
        """Get the maximum depth of the trie."""
        def _depth(node: CotTrieNode) -> int:
            if not node.children:
                return 1
            return 1 + max(_depth(child) for child in node.children)
        return _depth(self.root)
    
    def count_incorrect_steps(self) -> int:
        """Count the number of incorrect steps in the trie."""
        def _count_incorrect(node: CotTrieNode) -> int:
            count = 1 if node.content.correct == Correctness.INCORRECT else 0
            return count + sum(_count_incorrect(child) for child in node.children)
        return _count_incorrect(self.root)
    
    def has_explanation(self) -> bool:
        """Check if the trie has any explanation.
        Some legacy tries don't have explanations.
        """
        def _has_explanation(node: CotTrieNode) -> bool:
            return node.content.explanation is not None or any(
                _has_explanation(child) for child in node.children
            )
        return _has_explanation(self.root)
    
    def find_paths(self, condition: Callable[[CotTrieNode], bool], *, leaf_node_condition: Callable[[CotTrieNode], bool] = None) -> List[CotPath]:
        """
        Find all minimal paths through the trie that visit nodes matching the condition.
        Also include paths that end in a leaf node condition.
        
        Args:
            condition: Function that takes a CotTrieNode and returns bool
            
        Returns:
            List of CotPaths that cover all nodes matching the condition.
            These explicitly return deep copies of the nodes in the path.
        """
        paths: List[CotPath] = []
        node_status: Dict[CotTrieNode, NodeVisitStatus] = {}
        
        def _traverse(
            node: CotTrieNode,
            current_path: List[CotTrieNode]
        ):
            # Initialize node status if not seen
            if node not in node_status:
                node_status[node] = NodeVisitStatus.UNVISITED
            
            # Add node to current path
            current_path.append(node)
            
            # Check condition and mark node if it matches
            if condition(node) and node_status[node] == NodeVisitStatus.UNVISITED:
                node_status[node] = NodeVisitStatus.VISITING
             
            # If we hit a leaf, check if path contains any visiting nodes
            if node.terminal:
                has_visiting = any(
                    node_status.get(n) == NodeVisitStatus.VISITING 
                    for n in current_path
                )

                # Check the leaf node condition if provided. This will ensure that
                # trees with end segments like FAITHFUL -> [INCORRECT, CORRECT] will end up cutting two separate paths.
                # Without this check, we might visit (FAITHFUL -> INCORRECT) first, mark FAITHFUL as visited,
                # and then (FAITHFUL -> CORRECT) would be ignored.
                if has_visiting and (leaf_node_condition is None or leaf_node_condition(node)):
                    # Create new path and mark nodes as visited
                    paths.append(CotPath(nodes=current_path[:]))
                    for n in current_path:
                        if node_status[n] == NodeVisitStatus.VISITING:
                            node_status[n] = NodeVisitStatus.VISITED
            
            # Recursively traverse children
            for child in node.children:
                _traverse(child, current_path)
            
            # Remove node from current path when backtracking
            current_path.pop()
        
        # Start traversal from root
        _traverse(self.root, [])
        return paths
    
    def find_incorrect_paths(self) -> List[CotPath]:
        """Find all paths containing incorrect steps."""
        return self.find_paths(
            lambda node: node.content.correct == Correctness.INCORRECT,
            leaf_node_condition=self.leaf_node_unfaithfulness_condition
        )
    
    def find_incorrect_or_unfaithful_paths(self) -> List[CotPath]:
        """Find all paths containing incorrect or unfaithful steps.
        
        This is necessary to capture paths where all steps are correct in the first evaluation
        but some step is marked as unfaithful in the secondary evaluation."""

        return self.find_paths(
            lambda node: node.content.correct == Correctness.INCORRECT or self.unfaithfulness_condition(node),
            leaf_node_condition=self.leaf_node_unfaithfulness_condition
        )
    
    def leaf_node_unfaithfulness_condition(self, node: CotTrieNode) -> bool:
        """Check if a leaf node has a correct answer."""
        return node.content.answer_correct and node.content.answer_correct.correct == Correctness.CORRECT

    def unfaithfulness_condition(self, node: CotTrieNode) -> bool:
        """Check if a node is unfaithful."""
        return node.content.secondary_eval and \
            any(eval_.status == ProblemCode.UNFAITHFUL and eval_.severity in \
                (None, SeverityCode.MINOR, SeverityCode.MAJOR, SeverityCode.CRITICAL, SeverityCode.UNKNOWN) for eval_ in node.content.secondary_eval.evaluations)  # noqa: F821
    
    def find_unfaithful_paths(self) -> List[CotPath]:
        """Find all paths containing unfaithful steps."""
        return self.find_paths(
            self.unfaithfulness_condition,
            leaf_node_condition=self.leaf_node_unfaithfulness_condition
        )

    def has_unfaithful_correct_path(self) -> bool:
        """Check if trie has unfaithful-to-correct path."""
        def check_path(path: CotPath) -> bool:
            if path.nodes[-1].content.answer_correct.correct.value != "correct":
                return False
            unfaithful_count = sum(
                1 for node in path.nodes
                if self.unfaithfulness_condition(node)
            )
            return unfaithful_count >= 1

        all_paths = self.find_unfaithful_paths()
        return any(check_path(path) for path in all_paths)
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "root": self.root.serialize()
        }

if __name__ == "__main__":
    # Example usage
    example_trie = {
        "root": {
            "content": {
                "steps": ["Let's solve this step by step"],
                "correct": "correct",
                "explanation": None,
                "answer_correct": None
            },
            "children": [
                {
                    "content": {
                        "steps": ["First, calculate X"],
                        "correct": "incorrect",  # Make this step incorrect
                        "explanation": "This step is invalid",
                        "answer_correct": None
                    },
                    "children": [],
                    "terminal": True,
                    "prefix": "Let's solve this step by step\nFirst, calculate X"
                }
            ],
            "terminal": False,
            "prefix": "Let's solve this step by step"
        }
    }
    
    trie = CotTrie(example_trie)
    incorrect_paths = trie.find_incorrect_paths()
    print("Found incorrect paths:")
    for i, path in enumerate(incorrect_paths, 1):
        print(f"\nPath {i}:")
        print(path) 