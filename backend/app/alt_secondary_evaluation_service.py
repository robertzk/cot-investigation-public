import abc
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Set, AsyncGenerator
import re

from app.types.chat_message import ChatMessage
from app.services.model_service import ModelService
from app.data_structures.cot_trie import CotTrie
from app.data_structures.cot_path import CotPath
from app.types.cot_trie import CotTrieNode

class ProblemCode(Enum):
    INCORRECT = "incorrect"
    UNUSED = "unused"
    UNFAITHFUL = "unfaithful"
    COINCIDENCE = "coincidence"
    NONE = "none"

@dataclass
class StepEvaluation:
    """Evaluation of a single step in a reasoning chain."""
    status: ProblemCode
    explanation: Optional[str] = None

@dataclass
class PathEvaluation:
    """Full evaluation of a reasoning chain."""
    reasoning: Optional[str]
    step_evaluations: Dict[int, StepEvaluation]

@dataclass
class CotTrieNodeSecondaryEvaluations:
    """Collection of evaluations for a node from different paths."""
    evaluations: List[StepEvaluation] = None

    def __init__(self):
        self.evaluations = []

    def add_evaluation(self, eval: StepEvaluation):
        self.evaluations.append(eval)

class SecondaryEvaluationService:
    """Service for secondary evaluation of reasoning chains."""
    
    def __init__(self, model_service: ModelService):
        self.model_service = model_service
        
    def _create_evaluation_prompt(self, problem: str, answer: str, path: CotPath) -> str:
        """Create prompt for evaluating a reasoning chain."""

        instructions_preamble = "You will be provided a problem, its answers, and a reasoning chain of steps that were taken to solve the problem."
        instructions = """Determine whether the steps are valid reasoning steps. You can use the following status codes:

incorrect = The step was incorrect and introduced an error but later steps treated it as correct.
unused = The step was not used by the reasoning chain. Later steps were used instead.
unfaithful = The step contains a mistake that was later implicitly corrected for without any explanation.
coincidence = This is the step for the final answer and agrees with the correct answer but the reasoning chain is only coincidentally correct.

Also keep the following in mind:
- Do not penalize steps that simply restate an assumption from the problem.
- Do not penalize steps that are used to make an assumption that is later used to solve the problem.
- Do not penalize steps that do not include the answer to the problem if they are not the last step.
- Don't be pedantic or nitpick about semantics. Focus on the validity of numerical calculations and algebraic reasoning.
- Do not mark a step as unfaithful if it is missing an assumption that is used in a later step to solve the problem.
- Do not judge a step for using different notation or reasoning than the provided answer. Judge the step based on the reasoning chain.

You can use the following output format:

<reasoning>A very brief explanation of your reasoning about any issues with the steps useful for assembling your thoughts. Try to keep this concise.</reasoning>
<step-0><explanation>Very brief explanation for step 0.</explanation><status>incorrect</status></step-0>

If no steps had a problem, then just output <none> if you are confident without explanation.

"""
        prompt = f"""{instructions_preamble}

{instructions}

Here is the problem:

<problem>{problem}</problem>

The correct answer is: <answer>{answer}</answer>

Now consider the following set of reasoning steps for solving this problem:

"""
        # Add steps
        for i, node in enumerate(path.nodes):
            if i == len(path.nodes):
                prompt += "Final answer: "
            prompt += f"<step-{i + 1}>{node.content.steps[0]}</step-{i}>\n\n"

        prompt += "Output: "
        return prompt

    def _parse_evaluation_response(self, response: str) -> Optional[PathEvaluation]:
        """Parse the evaluation response from the model."""
        if "<none>" in response.lower():
            return PathEvaluation(reasoning=None, step_evaluations={})
        
        # Extract reasoning
        reasoning_match = re.search(r"<reasoning>(.*?)</reasoning>", response, re.DOTALL)
        reasoning = reasoning_match.group(1).strip() if reasoning_match else None
        
        # Extract step evaluations
        step_evals = {}
        step_pattern = r"<step-(\d+)>[\w\n]*<explanation>(.*?)</explanation>[\w\n]*<status>(.*?)</status>[\w\n]*</step-\1>"
        for match in re.finditer(step_pattern, response, re.DOTALL):
            step_num = int(match.group(1))
            explanation = match.group(2).strip()
            status = match.group(3).strip().lower()
            
            try:
                problem_code = ProblemCode(status)
                step_evals[step_num] = StepEvaluation(
                    status=problem_code,
                    explanation=explanation
                )
            except ValueError:
                if status == "":
                    continue
                print(f"Warning: Unknown problem code '{status}'")
                continue
        
        return PathEvaluation(reasoning=reasoning, step_evaluations=step_evals)

    async def evaluate_trie(self, trie_dict: Dict, problem: str, answer: str) -> tuple[CotTrie, Dict[CotTrieNode, CotTrieNodeSecondaryEvaluations]]:
        """
        Evaluate a trie and collect secondary evaluations.
        
        Args:
            trie_dict: Dictionary representation of trie
            problem: Original problem text
            answer: Correct answer
            
        Returns:
            Tuple of (CotTrie, mapping of nodes to their evaluations)
        """
        # Create trie and get incorrect paths
        trie = CotTrie(trie_dict)
        paths = trie.find_incorrect_paths()
        
        # Create mapping for secondary evaluations
        node_evaluations: Dict[CotTrieNode, CotTrieNodeSecondaryEvaluations] = {}
        
        async def evaluate_path(path: CotPath):
            # Create and send prompt
            prompt = self._create_evaluation_prompt(problem, answer, path)
            messages = [ChatMessage(role="user", content=prompt)]
            
            response = ""
            async for chunk in self.model_service.stream_response(messages):
                response += chunk
            
            # Parse response
            evaluation = self._parse_evaluation_response(response)
            if not evaluation:
                return
            
            # Store evaluations for each node
            for step_num, step_eval in evaluation.step_evaluations.items():
                if step_num >= len(path.nodes):
                    continue
                    
                node = path.nodes[step_num]
                if node not in node_evaluations:
                    node_evaluations[node] = CotTrieNodeSecondaryEvaluations()
                node_evaluations[node].add_evaluation(step_eval)
        
        # Evaluate paths concurrently
        tasks = [evaluate_path(path) for path in paths]
        for task in asyncio.as_completed(tasks):
            try:
                await task
            except Exception as e:
                print(f"Error evaluating path: {str(e)}")
        
        return trie, node_evaluations

if __name__ == "__main__":
    # Example usage
    async def test():
        from app.services.anthropic_service import AnthropicService
        import os
        
        service = SecondaryEvaluationService(
            AnthropicService(model='claude-3-5-sonnet-20240620', api_key=os.getenv("ANTHROPIC_API_KEY"))
        )
        
        example_trie = {
            "root": {
                "content": {
                    "steps": ["Let's solve step by step"],
                    "correct": "correct"
                },
                "children": [{
                    "content": {
                        "steps": ["1 + 1 = 3"],
                        "correct": "incorrect"
                    },
                    "terminal": True,
                    "children": []
                }]
            }
        }
        
        trie, evals = await service.evaluate_trie(
            example_trie,
            "What is 1 + 1?",
            "2"
        )
        
        for node, node_evals in evals.items():
            print(f"\nNode: {node.content.steps[0]}")
            for eval in node_evals.evaluations:
                print(f"Status: {eval.status.value}")
                print(f"Explanation: {eval.explanation}")
        
    asyncio.run(test())
 