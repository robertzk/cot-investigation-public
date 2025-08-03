from app.types import ChatMessage
import abc
from typing import AsyncGenerator, List

class ModelService(abc.ABC):
    @abc.abstractmethod
    async def stream_response(self, messages: List[ChatMessage], max_tokens: int = 1000, **kwargs) -> AsyncGenerator[str, None]:
        raise NotImplementedError("stream_response must be implemented by subclasses")

    @abc.abstractmethod
    def format_assistant_message(self, message: str) -> ChatMessage:
        raise NotImplementedError("format_assistant_message must be implemented by subclasses")
