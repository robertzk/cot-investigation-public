from dataclasses import dataclass
from typing import List, Set, Callable, Optional
from enum import Enum

from app.types.cot_trie import CotTrieNode

class NodeVisitStatus(Enum):
    UNVISITED = "unvisited"
    VISITING = "visiting"
    VISITED = "visited"

@dataclass
class CotPath:
    """
    Represents a path through a Chain of Thought trie.
    Contains nodes from root to leaf that satisfy some condition.
    """
    nodes: List[CotTrieNode]
    
    @property
    def length(self) -> int:
        return len(self.nodes)
    
    def is_unfaithful(self) -> bool:
        return any(node.content.secondary_eval.status == 'unfaithful' and node.content.secondary_eval.severity in ('major', 'critical') for node in self.nodes)
    
    @property
    def is_valid(self) -> bool:
        """Check if path is valid (starts at root, ends at leaf)."""
        if not self.nodes:
            return False
        return self.nodes[-1].terminal
    
    def __str__(self) -> str:
        return "\n".join(
            f"Step {i+1}: {node.content.steps[0]}"
            for i, node in enumerate(self.nodes)
        ) 
