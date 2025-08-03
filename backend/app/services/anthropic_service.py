from anthropic import AsyncAnthropic, HUMAN_PROMPT, AI_PROMPT, RateLimitError
from anthropic.types import Message
from typing import AsyncGenerator, List, Optional
from app.services.model_service import ModelService
from app.types import ChatMessage
import asyncio
import random
import time

DEFAULT_MODEL = 'claude-3-5-sonnet-20241022'

class AnthropicService(ModelService):
    AVAILABLE_MODELS = [
        'claude-3-5-sonnet-20241022',
        'claude-3-opus-20240229',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307'
    ]
    
    def __init__(self, api_key: str, model: Optional[str] = DEFAULT_MODEL, max_parallel_requests: int = 20):
        """
        Initialize the Anthropic service.
        
        Args:
            api_key: Anthropic API key
            max_parallel_requests: Maximum number of parallel requests (default 20, don't increase)
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.semaphore = asyncio.Semaphore(max_parallel_requests)
        
        if model is not None and model not in AnthropicService.AVAILABLE_MODELS:
            raise ValueError(f"Model {model} not in available models: {AnthropicService.AVAILABLE_MODELS}")
        self.default_model = model 

    def _format_few_shot_examples(self, examples: List[tuple[str, str]]) -> List[dict]:
        """
        Format few-shot examples for the API.
        
        Args:
            examples: List of (prompt, response) tuples
        Returns:
            Formatted messages list for the API
        """
        messages = []
        for prompt, response in examples:
            if HUMAN_PROMPT in prompt or AI_PROMPT in response:
                raise ValueError("Prompts should not contain HUMAN_PROMPT or AI_PROMPT separators")
                
            messages.extend([
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                },
                {
                    "role": "assistant", 
                    "content": [{"type": "text", "text": response}]
                }
            ])
        return messages

    async def _make_request(
        self,
        messages: List[dict],
        model: str = "claude-3-5-sonnet-20240620",
        max_retries: int = 5,
        max_tokens: int = 1000,
        temperature: float = 0
    ) -> Message:
        """
        Make a single request to the Anthropic API with retry logic.
        """
        if model not in AnthropicService.AVAILABLE_MODELS:
            raise ValueError(f"Model {model} not in available models: {AnthropicService.AVAILABLE_MODELS}")

        async with self.semaphore:
            for attempt in range(max_retries):
                try:
                    start = time.time()
                    response = await self.client.with_options(max_retries=max_retries).messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        messages=messages
                    )
                    print(f"Got response from {model} after {time.time() - start:.2f}s")
                    return response
                    
                except RateLimitError as e:
                    if attempt == max_retries - 1:
                        raise
                    
                    wait_time = (2 ** attempt) + random.random()
                    print(f"Rate limit error: {e}. Retrying in {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)

        raise RuntimeError("Failed after max retries")

    async def get_completion(
        self,
        prompt: str,
        few_shot_examples: Optional[List[tuple[str, str]]] = None,
        **kwargs
    ) -> Message:
        """
        Get a completion for a single prompt, optionally with few-shot examples.
        
        Args:
            prompt: The prompt to send
            few_shot_examples: Optional list of (prompt, response) tuples for few-shot learning
            **kwargs: Additional arguments to pass to the API call
        """
        messages = []
        if few_shot_examples:
            messages.extend(self._format_few_shot_examples(few_shot_examples))
            
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        })
        
        return await self._make_request(messages, **kwargs)

    async def get_completions(
        self,
        prompts: List[str],
        few_shot_examples: Optional[List[tuple[str, str]]] = None,
        **kwargs
    ) -> List[Message]:
        """
        Get completions for multiple prompts in parallel.
        
        Args:
            prompts: List of prompts to send
            few_shot_examples: Optional list of (prompt, response) tuples for few-shot learning
            **kwargs: Additional arguments to pass to the API calls
        """
        tasks = [
            self.get_completion(prompt, few_shot_examples, **kwargs)
            for prompt in prompts
        ]
        return await asyncio.gather(*tasks) 
    
    async def stream_response(self, messages: List[ChatMessage], max_tokens: int = 1000, model: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        Stream a response from the Anthropic API.

        Args:
            prompt: The prompt to send
            **kwargs: Additional arguments to pass to the API call
        """
        if model is None:
            model = self.default_model
            if model is None:
                raise ValueError("No model specified and no default model set")

        try:
            async with self.client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                messages=self._format_messages(messages),
                **kwargs
            ) as stream:
                async for chunk in stream.text_stream:
                    yield chunk
            
        except Exception as e:
            print(f"Error streaming response: {e}")
            raise
    
    def format_assistant_message(self, message: str) -> ChatMessage:
        return ChatMessage(role="assistant", content=message)

    @staticmethod
    def _format_messages(messages: List[ChatMessage]) -> List[dict]:
        return [
            {"role": message.role, "content": message.content}
            for message in messages
        ]

if __name__ == "__main__":
    import os
    anthropic_service = AnthropicService(os.environ["ANTHROPIC_API_KEY"])
    
    async def main():
        example_prompt = "What is the best type of cow and why?"
        buffer = ""

        tokens = 0
        async for chunk in anthropic_service.stream_response([ChatMessage(role="user", content=example_prompt)], model="claude-3-5-sonnet-20240620"):
            print(f"Token: {tokens}")
            buffer += chunk
            tokens += 1
            if tokens > 100:
                break
        
        print(f"Final response: {buffer}")

    asyncio.run(main())
