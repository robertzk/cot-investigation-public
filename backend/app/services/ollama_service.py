import os
import json
import asyncio
import aiohttp
from typing import AsyncGenerator, List, Optional, Dict, Any
from app.services.model_service import ModelService
from app.types import ChatMessage

class OllamaModelService(ModelService):
    """Service for interacting with Ollama API."""

    @classmethod
    async def create(cls, model_name: str, api_url: Optional[str] = None):
        """Create an instance of the OllamaModelService."""
        instance = cls(model_name, api_url, secret_password="blubber fish")
        await instance.start_stream()
        return instance
    
    def __init__(self, model_name: str, api_url: Optional[str] = None, *, secret_password: Optional[str] = None):
        """
        Initialize Ollama service.
        
        Args:
            model_name: Name of the model to use
            api_url: Base URL for Ollama API. Defaults to OLLAMA_API_URL env var.
        """
        # Prevent calling __init__ directly
        if secret_password != "blubber fish":
            raise ValueError("Please use the create method to instantiate this class.")

        
        self.api_url = api_url or os.getenv("OLLAMA_API_URL")
        if not self.api_url:
            raise ValueError("OLLAMA_API_URL environment variable not set")
        
        if not self.api_url.endswith("/"):
            self.api_url += "/"
            
        self.model_name = model_name
        self.default_params = {
            "temperature": 0.7,
            "seed": None
        }
    
    async def _verify_model(self):
        """Check if model is available, pull if not."""
        async with aiohttp.ClientSession() as session:
            # Check available models
            async with session.get(f"{self.api_url}tags") as response:
                if response.status != 200:
                    raise RuntimeError(f"Failed to get model tags: {await response.text()}")
                tags = await response.json()
                models = [model["name"] for model in tags["models"]]
                
                if self.model_name not in models:
                    print(f"Model {self.model_name} not found. Attempting to pull...")
                    # Pull the model
                    async with session.post(
                        f"{self.api_url}pull",
                        json={"name": self.model_name}
                    ) as pull_response:
                        if pull_response.status != 200:
                            raise RuntimeError(f"Failed to pull model: {await pull_response.text()}")
                        # Stream the pull progress
                        async for line in pull_response.content:
                            progress = json.loads(line)
                            if "status" in progress:
                                print(f"Pull progress: {progress['status']}")
    
    def _format_prompt(self, messages: List[ChatMessage]) -> str:
        """Format chat messages into a prompt string."""
        formatted = []
        for msg in messages:
            if msg.role == "user":
                formatted.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                formatted.append(f"Assistant: {msg.content}")
            else:
                formatted.append(f"{msg.role.capitalize()}: {msg.content}")
        return "\n".join(formatted)

    def _format_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Format chat messages into a list of dictionaries for the Ollama API."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    async def start_stream(self):
        # Verify model availability on init
        await self._verify_model()

    async def stream_response(
        self,
        messages: List[ChatMessage],
        max_tokens: int = 5_000,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from Ollama.
        
        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            seed: Random seed for reproducibility
            **kwargs: Additional generation parameters
        """

        try:
            #prompt = self._format_prompt(messages)
            
            # Prepare generation parameters
            params = {
                "model": self.model_name,
                # "prompt": prompt,
                "messages": self._format_messages(messages),
                "stream": True,
                "options": {
                    **self.default_params,
                    **({"temperature": temperature} if temperature is not None else {}),
                    **({"seed": seed} if seed is not None else {}),
                    **kwargs
                }
            }
            
            buffer = ""
            token_count = 0
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}chat",
                    json=params
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Generation failed: {await response.text()}")
                    
                    async for line in response.content:
                        if not line.strip():
                            continue
                            
                        try:
                            data = json.loads(line)
                            if "error" in data:
                                raise RuntimeError(f"Generation error: {data['error']}")
                            
                            if "response" in data:
                                buffer += data["response"]
                                token_count += 1
                            elif "message" in data:
                                buffer += data["message"]["content"]
                                token_count += 1
                                
                            # Yield in blocks of 50 tokens
                            if token_count % 50 == 0:
                                yield buffer
                                buffer = ""
                                
                            if data.get("done", False) or token_count >= max_tokens:
                                if buffer:  # Yield any remaining tokens
                                    yield buffer
                                break
                                
                        except json.JSONDecodeError:
                            print(f"Failed to parse response line: {line}")
                            continue
                            
        except Exception as e:
            print(f"Error in stream_response: {str(e)}")
            raise

    def format_assistant_message(self, message: str) -> ChatMessage:
        """Format a message as coming from the assistant."""
        return ChatMessage(role="assistant", content=message)


if __name__ == "__main__":
    async def test_ollama():
        service = await OllamaModelService.create("gemma2:2b")
        initial_message = """Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?\nWrite down your answer step by step, and number each step ("1.", "2.", etc.)."""
        messages = [
            ChatMessage(
                role="user",
                content=initial_message
            )
        ]
        
        print("Generating response...")
        async for chunk in service.stream_response(
            messages,
            temperature=0.8,
            seed=42
        ):
            print(chunk, end="", flush=True)
        print("\nDone!")

    asyncio.run(test_ollama()) 