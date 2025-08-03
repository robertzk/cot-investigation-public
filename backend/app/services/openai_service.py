from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from typing import AsyncGenerator, List, Optional, Dict, Any
from app.services.model_service import ModelService
from app.types import ChatMessage
import asyncio
import random
import time

DEFAULT_MODEL = 'o1-preview'

class OpenAIService(ModelService):
    AVAILABLE_MODELS = [
        'o1-preview',
        'gpt-4-0125-preview',  # GPT-4 Turbo
        'gpt-4-1106-preview',  # Previous GPT-4 Turbo
        'gpt-4',               # Base GPT-4
        'gpt-3.5-turbo-0125',  # Latest GPT-3.5
        'gpt-3.5-turbo'        # Auto-updating GPT-3.5
    ]
    
    def __init__(self, api_key: str, model: Optional[str] = DEFAULT_MODEL, max_parallel_requests: int = 20):
        """
        Initialize the OpenAI service.
        
        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4-0125-preview)
            max_parallel_requests: Maximum number of parallel requests
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.semaphore = asyncio.Semaphore(max_parallel_requests)
        
        if model is not None and model not in OpenAIService.AVAILABLE_MODELS:
            raise ValueError(f"Model {model} not in available models: {OpenAIService.AVAILABLE_MODELS}")
        self.default_model = model

    def _format_few_shot_examples(self, examples: List[tuple[str, str]]) -> List[Dict[str, str]]:
        """Format few-shot examples for the API."""
        messages = []
        for prompt, response in examples:
            messages.extend([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response}
            ])
        return messages

    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        max_retries: int = 5,
        max_tokens: int = 1000,
        temperature: float = 0
    ) -> ChatCompletion:
        """Make a single request to the OpenAI API with retry logic."""
        if model not in OpenAIService.AVAILABLE_MODELS:
            raise ValueError(f"Model {model} not in available models: {OpenAIService.AVAILABLE_MODELS}")

        for attempt in range(max_retries):
            try:
                start = time.time()
                async with self.semaphore:
                    response = await self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_completion_tokens=max_tokens,
                        temperature=temperature
                    )

                print(f"Got response from {model} after {time.time() - start:.2f}s")
                return response
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                wait_time = (2 ** attempt) + random.random()
                print(f"API error: {e}. Retrying in {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)

        raise RuntimeError("Failed after max retries")

    async def get_completion(
        self,
        prompt: str,
        few_shot_examples: Optional[List[tuple[str, str]]] = None,
        **kwargs
    ) -> ChatCompletionMessage:
        """Get a completion for a single prompt."""
        messages = []
        if few_shot_examples:
            messages.extend(self._format_few_shot_examples(few_shot_examples))
            
        messages.append({"role": "user", "content": prompt})
        
        response = await self._make_request(messages, **kwargs)
        return response.choices[0].message

    async def get_completions(
        self,
        prompts: List[str],
        few_shot_examples: Optional[List[tuple[str, str]]] = None,
        **kwargs
    ) -> List[ChatCompletionMessage]:
        """Get completions for multiple prompts in parallel."""
        tasks = [
            self.get_completion(prompt, few_shot_examples, **kwargs)
            for prompt in prompts
        ]
        return await asyncio.gather(*tasks)

    async def stream_response(
        self, 
        messages: List[ChatMessage], 
        max_tokens: int = 10_000, 
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the OpenAI API."""
        if model is None:
            model = self.default_model
            if model is None:
                raise ValueError("No model specified and no default model set")

        formatted_messages = self._format_messages(messages)

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                max_completion_tokens=9999, #max_tokens,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"Error streaming response: {e}")
            print(f"Full error details: {str(e)}")
            raise

    def format_assistant_message(self, message: str) -> ChatMessage:
        return ChatMessage(role="assistant", content=message)

    @staticmethod
    def _format_messages(messages: List[ChatMessage]) -> List[Dict[str, str]]:
        return [
            {"role": message.role, "content": [ { "type": "text", "text": message.content } ]}
            for message in messages
        ]

if __name__ == "__main__":
    import os
    openai_service = OpenAIService(os.environ["OPENAI_API_KEY"])
    
    async def main():
        example_prompt = "What is the best type of cow and why?"
        buffer = ""

        tokens = 0
        async for chunk in openai_service.stream_response(
            [ChatMessage(role="user", content=example_prompt)],
            model="o1-preview"
        ):
            buffer += chunk
            tokens += 1
            if tokens > 100:
                break
        
        print(f"Final response: {buffer}")

    asyncio.run(main()) 