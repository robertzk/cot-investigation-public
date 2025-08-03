import asyncio
import numpy as np
from typing import Any, Callable, Dict, List, Optional
import queue

from app.data_structures.buffered_cot_stream import BufferedCotStream
from app.services.step_evaluation_service import BasicStepEvaluationService, StepEvaluationService, StepEvaluation
from app.types.chat_message import ChatMessage
from app.types.correctness import Correctness, CorrectnessEvaluation
from app.types.cot_trie import CotTrieNode, CotContent, CotTrieVisualizer
from app.services.model_service import ModelService
from app.services.anthropic_service import AnthropicService
from app.services.openai_service import OpenAIService
from app.services.local_model_service import LocalModelService
from app.services.ollama_service import OllamaModelService

class CotTrieBuilder:
    """
    This class is used to build and store a COT in a trie data structure.

    The trie is used to generate rollouts of the COT and step through the
    tree through coroutines to build up the trie asynchronously.

    At each branching point, several step rollouts are generated, and an
    evaluation model is used to evaluate the rollouts for (a) equivalence
    and (b) correctness. In particular, if two step rollouts are basically
    identical, we can associate them together into a single equivalence class.
    This is represented in the CoT trie by having them in the same CotContent.
    """

    def __init__(
        self,
        model_service: ModelService,
        evaluation_service: StepEvaluationService,
        messages: List[ChatMessage],
        answer: str = None,
        *,
        branching_factor: int = 2,
        step_rollout_kwarg_sampler: Callable[[], Dict[str, Any]] = None,
        **kwargs
    ):
        self.model_service = model_service
        self.evaluation_service = evaluation_service
        self.messages = messages
        self.branching_factor = branching_factor
        self.kwargs = kwargs
        self.root = None
        self.answer = answer
        self.step_rollout_kwarg_sampler = step_rollout_kwarg_sampler or (lambda: {})

        if isinstance(model_service, LocalModelService):
            self.streamer = BufferedCotStream(model_service, messages, **kwargs, record_input=True)
        else:
            self.streamer = BufferedCotStream(model_service, messages, **kwargs)
        self._next_node_id = 1  # Start from 1 since 0 might be confusing

    async def build(self):
        """
        Build the COT trie asynchronously.
        """
        if self.root is not None:
            raise ValueError("COT trie already built.")

        # Before the CoT starts, just take one step. We don't need to evaluate the
        # step for correctness or equivalence at this point.
        new_kwargs = self.step_rollout_kwarg_sampler()
        if isinstance(self.model_service, LocalModelService):
            (step, input), was_done = await self.streamer.single_step(**new_kwargs)
        else:
            step, was_done = await self.streamer.single_step(**new_kwargs)

        self.root = CotTrieNode(
            CotContent(steps=[step], correct=Correctness.CORRECT, args=[new_kwargs], step_indices=[1]), [], prefix=step, node_id=self._next_node_id
        )
        if isinstance(self.model_service, LocalModelService):
            self.root.meta = {"inputs": [input]}

        if was_done:
            return # No CoT took place.

        q = queue.Queue()
        q.put(self.root)
        try:
            while (node := q.get(block=False)) is not None:
                await self._build_children(node)
                for child in node.children:
                    if not child.terminal:
                        q.put(child)
        except queue.Empty:
            return

        self._next_node_id += 1

    async def _build_children(self, node: CotTrieNode):
        """
        Build the children of a node.
        """
        self.streamer.step_rollouts(True)
        self.streamer.set_assistant_prefix_and_reset_checkpoints([ChatMessage(role="assistant", content=node.prefix)])
        steps = []
        was_done_flags = []
        kwargs_list = []
        inputs_list = []
        
        # print(f"\n\nBuilding children for: {node.prefix}")
        for _ in range(self.branching_factor + 1): # Add one to account for the case where we don't get any new steps.
            # Note we cannot use an async loop here because the streamer
            # relies on a shared state. However, we can still use asyncio
            # to build multiple CoT tries concurrently.
            if len(steps) >= self.branching_factor:
                break
            new_kwargs = self.step_rollout_kwarg_sampler()
            step, was_done = await self.streamer.single_step(**new_kwargs)
            if isinstance(self.model_service, LocalModelService):
                step, input = step

            if step == "" or step in steps:
                # We have already seen this exact step before.
                continue
            if len(step) < len("\n\nStep 10: "):
                # Sometimes, the model misinterprets the prefix and goes straight to the 
                # next step. (e.g. when given "blah blah\n\n2. "), it will just return "\n\n3. ".
                # This is a good enough heuristic to avoid "empty" steps.
                continue

            steps.append(step)
            was_done_flags.append(was_done)
            if isinstance(self.model_service, LocalModelService):
                inputs_list.append(input)
            if new_kwargs and len(new_kwargs) > 0:
                kwargs_list.append(new_kwargs)
            else:
                kwargs_list.append(None)

        # Treat done steps and not done steps as separate branches.
        for was_done in set(was_done_flags):
            sub_steps = [step for i, step in enumerate(steps) if was_done_flags[i] == was_done]
            sub_args = [kwargs_list[i] for i in range(len(steps)) if was_done_flags[i] == was_done]
            if len(sub_args) == 0 or all(arg is None for arg in sub_args):
                sub_args = None

            # Evaluate the steps for correctness and equivalence.
            evaluations: List[StepEvaluation] = (
                await self.evaluation_service.evaluate(self.messages, node.prefix, sub_steps)
            )
            
            sub_inputs = [inputs_list[i] for i in range(len(steps)) if was_done_flags[i] == was_done]

            for evaluation in evaluations:
                terminal = was_done or evaluation.final

                if terminal and self.answer is not None:
                    # If the step is terminal, we need to evaluate the correctness of the step.
                    answer_correct = await self.evaluation_service.evaluate_correctness(evaluation.steps[0], self.answer)
                else:
                    answer_correct = None
                
                trie_node = CotTrieNode(
                    content=CotContent(
                        steps=evaluation.steps,
                        args=sub_args,
                        step_indices=evaluation.step_indices,
                        correct=Correctness(evaluation.correct.value),
                        explanation=evaluation.explanation,
                        answer_correct=answer_correct,
                        meta={"inputs": sub_inputs}
                    ),
                    children=[],
                    prefix=node.prefix + evaluation.steps[0],
                    terminal=terminal,
                    node_id=self._next_node_id,
                )

                if isinstance(self.model_service, LocalModelService):
                    trie_node.meta = {"input": sub_inputs}
 
                node.children.append(trie_node)

            self._next_node_id += 1
    
    def size(self) -> int:
        """
        Get the size of the trie.
        """
        def _size(node: CotTrieNode) -> int:
            return 1 + sum(_size(child) for child in node.children) if node.children else 1
        return _size(self.root)
    
    def depth(self) -> int:
        """
        Get the depth of the trie.
        """
        def _depth(node: CotTrieNode) -> int:
            return max(1 + _depth(child) for child in node.children) if node.children else 1
        return _depth(self.root)


if __name__ == "__main__":
    async def main():
        import os
        # Example model services:
        model_service = AnthropicService(api_key=os.environ["ANTHROPIC_API_KEY"], model='claude-3-haiku-20240307')
        # model_service = LocalModelService('google/gemma-2-2b-it')
        # model_service = await OllamaModelService.create("gemma2:2b")
        # model_service = OpenAIService(api_key=os.environ["OPENAI_API_KEY"], model="o1-preview")

        # evaluator_model = AnthropicService(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-3-5-sonnet-20240620")
        evaluator_model = OpenAIService(api_key=os.environ["OPENAI_API_KEY"], model="o1-preview")

        evaluation_service = BasicStepEvaluationService(evaluator_model)
        #cot_prompt = f"""Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?
#Write down your answer step by step, and number each step ("1.", "2.", etc.)."""
        cot_prompt = """Grace weighs 125 pounds. Alex weighs 2 pounds less than 4 times what Grace weighs. What are their combined weights in pounds?
Write down your answer step by step, and number each step ("1.", "2.", etc.)."""
        cot_prompt = """Kevin has a shoebox filled with toads.  Every day, Kevin feeds each toad 3 worms.  It takes Kevin 15 minutes to find each worm.  If it takes Kevin 6 hours to find enough worms to feed all of his toads, how many toads does Kevin have in his shoebox?
Write down your answer step by step, and number each step ("1.", "2.", etc.)."""

        if isinstance(evaluator_model, AnthropicService):
            step_rollout_kwarg_sampler = lambda: {"seed": np.random.randint(0, 1000000), "temperature": np.random.uniform(0.6, 0.8)}
        else:
            step_rollout_kwarg_sampler = None

        cot_trie_obj = CotTrieBuilder(model_service, evaluation_service, [ChatMessage(role="user", content=cot_prompt)], answer="Kevin has 8 toads in his shoebox.", branching_factor=4,
                            #step_rollout_kwarg_sampler=lambda: {"temperature": np.random.uniform(0.6, 0.8)})
                            step_rollout_kwarg_sampler=step_rollout_kwarg_sampler)
        await cot_trie_obj.build()


        # Add visualization test
        print("\nTrie Visualization:")
        print("==================")
        CotTrieVisualizer.print_trie(cot_trie_obj.root)

        import pdb; pdb.set_trace()

    asyncio.run(main())

