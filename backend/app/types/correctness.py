from enum import Enum
from dataclasses import dataclass
from typing import Optional

class Correctness(Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"

@dataclass
class CorrectnessEvaluation:
    correct: Correctness
    explanation: Optional[str] = None
