import re
from typing import AsyncGenerator, List, Optional, Tuple, Union
import asyncio
from itertools import product
import re
import torch
from transformer_lens import HookedTransformer
from transformer_lens.HookedTransformerConfig import HookedTransformerConfig
from app.services.model_service import ModelService
from app.types import ChatMessage
import random


def format_gemma_chat(messages: List[ChatMessage], *, leave_final_assistant_turn: bool = True) -> str:
    # As per the gemma instruct template: https://github.com/ollama/ollama/blob/3919f4ba3d0c40f50b4b89474e3306a900a15eed/template/gemma-instruct.gotmpl#L8
    """Format messages exactly as Ollama does for Gemma models."""
    if len(messages) == 0:
        return ""
    
    formatted = ""
    for i, msg in enumerate(messages):
        if msg.role == "user":
            formatted += f"<start_of_turn>user\n{msg.content}<end_of_turn>\n"
        elif msg.role == "assistant":
            if leave_final_assistant_turn and i == len(messages) - 1:
                formatted += f"<start_of_turn>model\n{msg.content}"
            else:
                formatted += f"<start_of_turn>model\n{msg.content}<end_of_turn>\n"
    
    if leave_final_assistant_turn and messages[-1].role == "assistant":
        return formatted

    formatted += "<start_of_turn>model\n"  # Add the final model turn
    return formatted

class LocalModelService(ModelService):
    """
    A service that uses TransformerLens for local model inference.
    """
    semaphore: asyncio.Semaphore = asyncio.Semaphore(1)
    
    def __init__(self, model_name: str = "gpt2-medium", device: str = "cuda" if torch.cuda.is_available() else "cpu", *,
                 temperature: float = 0.0, top_p: float = 0.9, max_new_tokens: int = 5_000):
        """
        Initialize the local model service.
        
        Args:
            model_name: Name of the model to load (must be compatible with TransformerLens)
            device: Device to run inference on ("cuda" or "cpu")
        """
        self.model = HookedTransformer.from_pretrained(
            model_name,
            device=device
        )
        self.device = device
        self.model_name = model_name
        self.semaphore = LocalModelService.semaphore # Use the same semaphore for all instances of LocalModelService
        # as we don't know the memory usage of the model and the input size.
        # This can probably be optimized by assessing the memory usage of the model and the input size.
        
        # Set common generation parameters
        self.default_params = {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
        }

        self.cot_instruction = None
    
    def set_cot_instruction(self, cot_instruction: str):
        self.cot_instruction = cot_instruction
    
    def _format_model_specific_prompt(self, messages: List[ChatMessage], model_name: Optional[str] = None) -> str:
        if model_name and re.match(r".*gemma-.*-it", model_name):
            return format_gemma_chat(messages)

    def _format_prompt(self, messages: List[ChatMessage], *, model_name: Optional[str] = None) -> str:
        """Format chat messages into a single prompt string."""
        prompt = self._format_model_specific_prompt(messages, model_name)
        if prompt is not None:
            return prompt

        formatted = []
        prev_role = None
        for msg in messages:
            if msg.role == "user":
                if prev_role == "user":
                    formatted.append("\n")
                else:
                    formatted.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                if prev_role == "assistant":
                    formatted.append("\n")
                else:
                    formatted.append(f"\nAssistant: {msg.content}")
            else:
                formatted.append(f"{msg.role.capitalize()}: {msg.content}")
            prev_role = msg.role
        
        if len(messages) > 0:
            if messages[-1].role == "assistant":
                return "\n".join(formatted)
            else:
                return "\n".join(formatted) + "\nAssistant:"
        else:
            return ""
        
    def _replace_cot_instruction(self, prompt: str, cot_instruction_seed: int) -> str:
        """
        Replace the cot instruction in an effort to generate some entropy in the model's
        response while keeping the deterministic reproducibility of the example with temperature 0.
        """
        if self.cot_instruction is None:
            raise ValueError("No cot instruction set. Use the set_cot_instruction method to set a cot instruction.")
        
        variations1 = {
            "Reason through your answer step by step, and number every step ",
            "Write down your answer by reasoning through it step by step. Number every step ",
            "Produce your answer by reasoning through it step by step. Number all steps ",
            "Construct an answer step by step, and enumerate all steps ",
            "Build your answer one step at a time, and number each of your steps ",
        }

        variations2 = {
            '("1.", "2.", etc.)',
            '("Step 1.", "Step 2.", etc.)',
            '("1: ", "2: ", etc.)',
            '("Step 1: ", "Step 2: ", etc.)',
        }

        all_variations = list(product(variations1, variations2))
        random.seed(cot_instruction_seed)
        chosen_variation = random.choice(all_variations)
        chosen_variation = chosen_variation[0] + chosen_variation[1] + '.'
        
        return prompt.replace(self.cot_instruction, chosen_variation)

    async def stream_response_with_input(self, *args, **kwargs) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Stream a response from the local model with a given input.
        """
        async for chunk, input in self.stream_response(*args, **kwargs, with_input=True):
            yield chunk, input

    async def stream_response(
        self, 
        messages: List[ChatMessage], 
        max_tokens: int = 1000,
        temperature: float = 0.0,
        *,
        with_input: bool = False,
        **kwargs,
    ) -> Union[AsyncGenerator[str, None], AsyncGenerator[Tuple[str, str], None]]:
        """
        Stream a response from the local model.
        
        Args:
            messages: List of chat messages
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional generation parameters
        """
        try:
            if "seed" in kwargs:
                seed = kwargs.pop("seed")
            else:
                seed = None
            
            if seed is not None:
                # TransformerLens does not allow for deterministic reproducibility
                # using seeds if temperature is not 0. However, we need non-zero
                # temperature for variance in the responses. We settle for prefixing
                # the seed to the problem statement.
                if messages[0].content.startswith("(Problem"):
                    new_content = re.sub(r"\(Problem \d+\)", f"(Problem {seed})", messages[0].content)
                else:
                    new_content = f"(Problem {seed}) {messages[0].content}"
                messages[0] = ChatMessage(role="user", content=new_content)
            
            if "cot_instruction_seed" in kwargs:
                cot_instruction_seed = kwargs.pop("cot_instruction_seed")
            else:
                cot_instruction_seed = None
            
            if cot_instruction_seed is not None:
                messages[0] = ChatMessage(role="user", content=self._replace_cot_instruction(messages[0].content, cot_instruction_seed))

            # Format messages into prompt
            prompt = self._format_prompt(messages, model_name=self.model_name)
            
            # Tokenize the prompt
            tokens = self.model.to_tokens(prompt, prepend_bos=True).to(self.device)
            
           # Generate tokens one at a time
            generated = None
            batch_size = 50
            finished = False

            # Set up generation parameters
            gen_params = {
                **self.default_params,
                "max_new_tokens": batch_size,
                "temperature": temperature,
                **kwargs
            }

            total_tokens = 0
            
            while True:
                # Get next token distribution
                input_tokens = torch.cat([tokens, generated], dim=-1) if generated is not None else tokens
                input_length = input_tokens.shape[-1]
                async with self.semaphore:
                    if seed is not None:
                        HookedTransformerConfig.set_seed_everywhere(None, seed)

                    with torch.inference_mode():
                        next_tokens = self.model.generate(
                            input_tokens,
                            verbose=False,
                            **gen_params
                        )
                    
                next_tokens = next_tokens[:, input_length:]

                # Ignore the first token as it is the BOS token which is sometimes the same as the EOS token.
                if (self.model.tokenizer.eos_token_id == next_tokens[0, 1:]).any(dim=-1).item():
                    # Cut off at the end of the sequence
                    # The +2 is to account for skipping the BOS token, and to account for inclusion of the EOS token.
                    next_tokens = next_tokens[:, :(next_tokens[0, 1:] == self.model.tokenizer.eos_token_id).nonzero(as_tuple=True)[0][0] + 2]
                    finished = True
                
                if next_tokens.shape[0] == 0:
                    # No more tokens generated. We likely went past the EOS token.
                    break

                generated = next_tokens if generated is None else torch.cat([generated, next_tokens], dim=-1)

                # Yield batch when it reaches batch_size
                if with_input:
                    yield self.model.to_string(next_tokens)[0], self.model.to_string(input_tokens)[0]
                else:
                    yield self.model.to_string(next_tokens)[0]
                total_tokens += next_tokens.shape[-1]

                if next_tokens.shape[-1] < batch_size or finished or total_tokens >= max_tokens:
                    break
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # Print relevant tensor shapes for debugging
            if 'input_tokens' in locals():
                print(f"input_tokens shape: {input_tokens.shape}")
            if 'next_tokens' in locals():
                print(f"next_tokens shape: {next_tokens.shape}")
            if 'generated' in locals():
                print(f"generated shape: {generated.shape}")
                
            # Add debugger breakpoint if running in interactive mode
            if hasattr(__builtins__, 'breakpoint'):
                breakpoint()

            print(f"Error in stream_response: {str(e)}")
            raise

    def format_assistant_message(self, message: str) -> ChatMessage:
        """Format a message as coming from the assistant."""
        return ChatMessage(role="assistant", content=message)

if __name__ == "__main__":
    async def test_local_model():
        service = LocalModelService(model_name="google/gemma-2-2b-it")
        initial_message = """Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?\nWrite down your answer step by step, and number each step ("1.", "2.", etc.)."""
        messages = [
            ChatMessage(role="user", content=initial_message)
        ]
        
        print("Generating response...")
        async for chunk in service.stream_response(messages):
            print(chunk, end="", flush=True)
        print("\nDone!")

    asyncio.run(test_local_model()) 