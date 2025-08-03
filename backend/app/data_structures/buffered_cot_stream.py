import asyncio
from typing import List, Optional, Tuple, Union

from app.services.model_service import ModelService
from app.types import ChatMessage
import abc

from app.services.anthropic_service import AnthropicService


class BufferedStream(abc.ABC):
    """
    This class is used to buffer a prompt into a stream with multiple checkpoints.

    You can use this class to manage a growing prompt and rollback to previous
    checkpoints. A heuristic is used to decide when to checkpoint the prompt.
    """

    def __init__(self, model_service: ModelService, messages: List[ChatMessage], use_step_rollouts: bool = False, *,
                 record_input: bool = False, **kwargs):
        self.model_service = model_service
        self.messages = messages
        self.started_once = False
        self.use_step_rollouts = use_step_rollouts
        self.assistant_prefix = []
        self.record_input = record_input

        self.common_gen_params = kwargs
        self.gen_params = {}

    def set_assistant_prefix_and_reset_checkpoints(self, assistant_prefix: List[ChatMessage]):
        """
        Set the assistant prefix and reset the buffer on the streamer as well
        as any checkpoints. Only works at the moment for prefixes that
        end at a checkpoint (i.e. CoT step).
        """
        self.next_checkpoint = 1
        # Use rstrip to prevent API error: "final assistant content cannot end with trailing whitespace"
        # This is an issue in the Anthropic API, not in our code.
        self.buffer = "".join([prefix.content for prefix in assistant_prefix]).rstrip()
        if len(assistant_prefix) > 0:
            assistant_prefix[-1].content = assistant_prefix[-1].content.rstrip()
        self.assistant_prefix = assistant_prefix
        while next_checkpoint := self._next_checkpoint(self.buffer[self.checkpoints[self.next_checkpoint - 1]:]):
            found_next_checkpoint, next_checkpoint_index = next_checkpoint
            if not found_next_checkpoint:
                self.checkpoints[self.next_checkpoint] = len(self.buffer)
                self.next_checkpoint += 1
                break
            else:
                # TODO: Think about whether buffer.rfind makes sense in the _next_checkpoint method.
                # For example, if we use "\n2. " earlier than the final occurence of "\n2. ", we would find the wrong checkpoint.
                self.checkpoints[self.next_checkpoint] = next_checkpoint_index
                self.next_checkpoint += 1
    
    def set_next_checkpoint(self, checkpoint_index: int):
        self.next_checkpoint = checkpoint_index
    
    def __aiter__(self):
        if self.started_once:
            self.prev_message = ""
        else:
            self.buffer = ""
            self.prev_message = ""
            self.next_checkpoint = 1
            self.checkpoints = {0: 0}
            self.started_once = True

        self.is_done = False
        
        self.streamer = self.model_service.stream_response(self.messages + self.assistant_prefix, **{**self.common_gen_params, **self.gen_params}, with_input=self.record_input)
        return self
    
    def rollback_to_checkpoint(self, checkpoint_index: Optional[int] = None):
        if checkpoint_index is None:
            checkpoint_index = self.next_checkpoint - 1

        if checkpoint_index not in self.checkpoints:
            raise ValueError(f"Checkpoint {checkpoint_index} not found")
        
        self.is_done = False
        self.buffer = self.buffer[:self.checkpoints[checkpoint_index]]
        for checkpoint in list(self.checkpoints.keys()):
            if checkpoint > checkpoint_index:
                del self.checkpoints[checkpoint]
        self.next_checkpoint = checkpoint_index + 1
        self._reset_streamer()
    
    def _reset_streamer(self):
        self.streamer = self.model_service.stream_response(self.messages + self.assistant_prefix, **{**self.common_gen_params, **self.gen_params}, with_input=self.record_input)
    
    async def __anext__(self) -> Union[Tuple[str, bool], Tuple[Tuple[str, str], bool]]:
        """
        Return a tuple of the next chunk of the stream and a boolean indicating
        whether the stream was done on that step (due to step rollouts being enabled,
        the stream may have been automatically rolled back to a previous checkpoint).
        """
        if self.is_done:
            raise StopAsyncIteration

        current_checkpoint = self.checkpoints[self.next_checkpoint - 1]
        any_message_received = False
        input = None
        async for message in self.streamer:
            if self.record_input:
                message, input = message

            any_message_received = True
            # Check if the message indicates a new checkpoint. Include the previous message
            # to account for cases where the checkpoint is split across two messages
            # (e.g., "\n[end]2.")
            self.buffer += message
            is_next_checkpoint, checkpoint_index = self._next_checkpoint("".join([self.prev_message, message]))
            self.prev_message = message

            if is_next_checkpoint:
                if self.use_step_rollouts:
                    current_message = self.buffer[self.checkpoints[self.next_checkpoint - 1]:checkpoint_index]
                    self.checkpoints[self.next_checkpoint] = checkpoint_index
                    # Roll back the buffer to the previous checkpoint
                    self.buffer = self.buffer[:self.checkpoints[self.next_checkpoint - 1]]
                    self._reset_streamer()
                    if self.record_input:
                        return (current_message, input), False
                    else:
                        return current_message, False
                else:
                    self.checkpoints[self.next_checkpoint] = checkpoint_index
                    previous_checkpoint = self.next_checkpoint - 1
                    self.next_checkpoint += 1
                    if self.record_input:
                        return (self.buffer[self.checkpoints[previous_checkpoint]:checkpoint_index], input), False
                    else:
                        return self.buffer[self.checkpoints[previous_checkpoint]:checkpoint_index], False
        else:
            if self.use_step_rollouts:
                current_message = self.buffer[current_checkpoint:]
                # Roll back the buffer to the previous checkpoint
                self.buffer = self.buffer[:current_checkpoint]
                self._reset_streamer()
                if self.record_input:
                    return (current_message, input), True
                else:
                    return current_message, True
            else:
                self.is_done = True
                if any_message_received:
                    if self.record_input:
                        return (self.buffer[current_checkpoint:], input), True
                    else:
                        return self.buffer[current_checkpoint:], True
                else:
                    raise StopAsyncIteration

    async def single_step(self, peek: bool = False, **kwargs) -> Union[Tuple[str, bool], Tuple[Tuple[str, str], bool]]:
        """
        Produce a single step of the COT. Do not use this method inside of
        an async for loop when already iterating over the streamer.
        """
        if peek:
            step_rollouts = self.use_step_rollouts
            self.step_rollouts(True)
        message = None
        # Take one step in the CoT.
        was_done = True
        try:
            self.gen_params = kwargs
            async for m, done in self:
                was_done = done
                message = m
                break
            else:
                return StopAsyncIteration
        finally:
            self.gen_params = {}

        if peek:
            self.step_rollouts(step_rollouts)
        
        return message, was_done

    def step_rollouts(self, use_step_rollouts: bool = True):
        """
        Determine whether to produce the same step repeatedly.
        """
        self.use_step_rollouts = use_step_rollouts

    @abc.abstractmethod
    def _next_checkpoint(self, message: str) -> Tuple[bool, Optional[int]]:
        """
        Returns true if the message indicates a new checkpoint, as well as the
        index into the buffer where the checkpoint is located.
        """
        raise NotImplementedError("Subclasses must implement this method")
    
class BufferedCotStream(BufferedStream):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def _next_checkpoint(self, message: str) -> Tuple[bool, Optional[int]]:
        """
        Determine if the message indicates a new checkpoint vis-a-vis 
        a new CoT step ("\n1.", "\n2.", etc.). If so, return the index of the
        checkpoint in the buffer in addition to True.
        """
        
        message_start_index = self.buffer.find(message)

        checkpoint_text_options = [f"\n{self.next_checkpoint}. ", f"\nStep {self.next_checkpoint}: ", f"\nStep {self.next_checkpoint}. ",
                                   f"\n{self.next_checkpoint}.\n", f"\nStep {self.next_checkpoint}:\n", f"\nStep {self.next_checkpoint}.\n",
                                   f"\n**{self.next_checkpoint}.** ", f"\n**Step {self.next_checkpoint}:** ", f"\n**Step {self.next_checkpoint}.** ",
                                   f"\n**{self.next_checkpoint}.**\n", f"\n**Step {self.next_checkpoint}:**\n", f"\n**Step {self.next_checkpoint}.**\n",
                                   f"\n**{self.next_checkpoint}. ", f"\n**Step {self.next_checkpoint}: ", f"\n**Step {self.next_checkpoint}. "]

        checkpoint_text, checkpoint_index = None, None
        for option in checkpoint_text_options:
            checkpoint_text = option
            checkpoint_index = self.buffer[message_start_index:].rfind(checkpoint_text)
            if checkpoint_index != -1:
                break

        if checkpoint_index != -1:
            return True, message_start_index + checkpoint_index + len(checkpoint_text)
        else:
            return False, None


if __name__ == "__main__":
    import os
    anthropic_service = AnthropicService(os.environ["ANTHROPIC_API_KEY"])
    
    async def main():
        cot_prompt = f"""Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?
Write down your answer step by step, and number each step ("1.", "2.", etc.)."""

        streamer = BufferedCotStream(anthropic_service, [ChatMessage(role="user", content=cot_prompt)], model="claude-3-5-sonnet-20240620")

        buffer = ""
        async for chunk, _ in streamer:
            print(chunk)
            buffer += chunk

        print(f"\n\nCheckpoints: {streamer.checkpoints}")
        print(f"\n\nBuffer: {buffer}")

        for checkpoint in streamer.checkpoints:
            print(f"\n\nCheckpoint {checkpoint}: {streamer.buffer[:streamer.checkpoints[checkpoint]]}")

        print("\n\n** Rolling back to checkpoint 1 for step rollouts check.")

        streamer.rollback_to_checkpoint(1)
        buffer = streamer.buffer[:streamer.checkpoints[1]]

        streamer.step_rollouts(True)

        count = 0
        async for chunk, _ in streamer:
            count += 1
            print(f"\n\nStep rollout {count}: {chunk}")
            if count > 3:
                break

        print("\n\n** Rolling back to checkpoint 1.")

        streamer.rollback_to_checkpoint(1)
        streamer.step_rollouts(False)
        buffer = streamer.buffer[:streamer.checkpoints[1]]
        async for chunk, _ in streamer:
            pass

        print(f"\n\nCheckpoints: {streamer.checkpoints}")
        print(f"\n\nBuffer: {streamer.buffer}")

        for checkpoint in streamer.checkpoints:
            print(f"\n\nCheckpoint {checkpoint}: {streamer.buffer[:streamer.checkpoints[checkpoint]]}")

        # TODO: Verify final buffer
        import pdb; pdb.set_trace()

    asyncio.run(main())


