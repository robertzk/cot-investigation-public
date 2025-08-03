import abc
import ast
from dataclasses import dataclass
from enum import Enum
from typing import List

from app.types.chat_message import ChatMessage
from app.services.model_service import ModelService
from app.services.anthropic_service import AnthropicService
from app.types.correctness import Correctness, CorrectnessEvaluation

class Correctness(Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"

@dataclass
class StepEvaluation:
    """
    A class that represents the evaluation of a step.
    """
    steps: List[str]
    step_indices: List[int]
    correct: Correctness
    final: bool=False
    explanation: str=None

@dataclass
class CorrectnessEvaluation:
    correct: Correctness
    explanation: str=None

class StepEvaluationService(abc.ABC):
    """
    A service that evaluates the correctness of a step in a CoT.
    """
    
    def __init__(self, model_service: ModelService):
        self.model_service = model_service
    
    @abc.abstractmethod
    def transform_messages(self, messages: List[ChatMessage], prefix: str, steps: List[str]) -> List[ChatMessage]:
        """
        Transform the messages for the evaluation model.

        Strive to produce the following output format:
            Output format: <explanation>...</explanation> <equivalent>[[1, 2], [4], [3, 5]]</equivalent> <correct>[correct, incorrect, uncertain]</correct> <final>[yes, no, no]</final>
        """
        raise NotImplementedError

    async def evaluate(self, messages: List[ChatMessage], prefix: str, steps: List[str]) -> List[StepEvaluation]:
        """
        Evaluate the correctness of a set of possibly equivalent steps in a CoT.
        """
        if len(steps) == 0:
            raise ValueError("No steps to evaluate")

        evaluation_messages = self.transform_messages(messages, prefix, steps)
        response = ""
        prev_chunk = ""
        async for chunk in self.model_service.stream_response(evaluation_messages):
            response += chunk
            if "</final>" in f"{prev_chunk}{chunk}":
                break
            prev_chunk = chunk

        # Parse the response into a list of StepEvaluation objects.
        # Output format: <explanation>...</explanation> <equivalent>[[1, 2], [4], [3, 5]]</equivalent> <correct>[correct, incorrect, uncertain]</correct> <final>[yes, no, no]</final>
        # Extract the equivalent groups from the response
        response = response.strip()

        explanation_end = response.find("</explanation>")
        explanation_str = response[:explanation_end]
        
        response = response[explanation_end:]
        equivalent_start = response.find("<equivalent>")
        equivalent_end = response.find("</equivalent>")
        equivalent_str = response[equivalent_start + len("<equivalent>"):equivalent_end]

        # Extract the correctness evaluations
        correct_start = response.find("<correct>[") + len("<correct>[")
        correct_end = response.find("]</correct>")
        correct_str = response[correct_start:correct_end]
        correctness_list = correct_str.split(", ")

        final_start = response.find("<final>[") + len("<final>[")
        final_list = []
        if final_start != -1:
            final_end = response.find("]</final>")
            final_str = response[final_start:final_end]
            final_list = final_str.split(", ")

        # Parse the equivalent groups string into a list of lists
        try:
            equivalent_groups = ast.literal_eval(equivalent_str)
        except SyntaxError:
            raise ValueError(f"Invalid equivalent string: {equivalent_str}")
            import pdb; pdb.set_trace()

        # Create StepEvaluation objects for each group
        evaluations = []
        for group_idx, group in enumerate(equivalent_groups):
            # Get all steps in this equivalence group
            group_steps = [steps[i-1] for i in group]
            # Get correctness for this group
            try:
                correct = Correctness(correctness_list[group_idx])
            except ValueError:
                correct = Correctness.UNCERTAIN
            except IndexError:
                raise ValueError(f"Incorrectness list length {len(correctness_list)} does not match number of equivalence groups {len(equivalent_groups)}")

            if len(final_list) > 0 and group_idx < len(final_list):
                final = final_list[group_idx]
            else:
                final = False

            evaluations.append(StepEvaluation(steps=group_steps, step_indices=group, correct=correct, final=final == "yes", explanation=explanation_str))

        return evaluations

    async def evaluate_correctness(self, step: str, answer: str) -> CorrectnessEvaluation:
        """
        Evaluate whether a step's answer matches the correct answer.
        
        Args:
            step: The step text to evaluate
            answer: The correct answer to compare against
        
        Returns:
            CorrectnessEvaluation with the result and explanation
        """
        prompt = f"""Compare the following step with the correct answer and determine if they match:

Step:
<step>{step}</step>

Correct Answer:
<answer>{answer}</answer>

Do these contain the same answer? Answer with <correct>yes</correct>, <correct>no</correct>, or <correct>uncertain</correct>.
Then explain your reasoning after a newline, being specific about the numbers involved.

Output format example:
<correct>yes</correct>
The step shows 42 apples which matches the correct answer of 42 apples.
"""
        messages = [ChatMessage(role="user", content=prompt), ChatMessage(role="assistant", content="<correct>")]
        response = ""
        async for chunk in self.model_service.stream_response(messages):
            response += chunk
        
        # Parse the response
        response = response.strip()
        
        correct_end = response.find("</correct>")
        correct = response[:correct_end]

        if correct not in ("yes", "no", "uncertain"):
            return CorrectnessEvaluation(
                correct=Correctness.UNKNOWN,
                explanation="Failed to parse model response"
            )
        
        explanation = response[correct_end + len("</correct>"):].strip()
        
        correctness_mapping = {
            "yes": Correctness.CORRECT,
            "no": Correctness.INCORRECT,
            "uncertain": Correctness.UNCERTAIN
        }
        
        return CorrectnessEvaluation(
            correct=correctness_mapping.get(correct, Correctness.UNKNOWN),
            explanation=explanation
        )

class BasicStepEvaluationService(StepEvaluationService):
    """
    A service that evaluates the correctness of a step in a CoT using Anthropic.
    """

    def __init__(self, model_service: ModelService):
        if not isinstance(model_service, ModelService):
            raise ValueError("model_service must be an instance of ModelService")
        super().__init__(model_service)

    def transform_messages(self, messages: List[ChatMessage], prefix: str, steps: List[str]) -> List[ChatMessage]:
        """
        Transform the messages for the evaluation model by wrapping them in appropriate tags.
        """
        prompt = """Consider the following conversation between a human and an AI assistant:\n\n<conversation>"""
        
        for message in messages:
            if message.role == "user":
                prompt += f"\n<human>{message.content}</human>"
            else:
                prompt += f"\n<assistant>{message.content}</assistant>"
                
        if prefix:
            prompt += f"\n<assistant>{prefix}</assistant>"

        prompt += "\n</conversation>\n\nIdentify which of the following continuations of the assistant's response " +\
            "are equivalent to each other, in the sense that they are logically completely equivalent. If they are equivalent, " +\
            "return the list of equivalent continuations. Make sure to include ALL continuations, even if they are unique by themselves. " +\
            "For each respective set of equivalent continuations, also return whether they are correct, incorrect, or uncertain.\n" + \
            "Also return if this is the final step for a given set of equivalent continuations." +\
            "State your reasoning in a way that is easy to understand and follow, and that is concise." +\
            "\nOutput format: <explanation>Continuations 1 and 2 are equivalent because they both follow the same logical steps. "+ \
            "Explanation 4 is different because it does X instead of Y. Etc. </explanation> "+ \
            "<equivalent>[[1, 2], [4], [3, 5]]</equivalent> <correct>[correct, incorrect, uncertain]</correct> <final>[yes, no, no]</final>\n\n"

        prompt += "The continuations are as follows:\n"
        for i, step in enumerate(steps):
            prompt += f"\n<continuation-{i+1}>{step}</continuation-{i+1}>\n"
        
        prompt += "\nOutput: "
        
        return [ChatMessage(role="user", content=prompt), ChatMessage(role="assistant", content="<explanation>")]
    
