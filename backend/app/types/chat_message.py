from dataclasses import dataclass

@dataclass
class ChatMessage:
    """
    A class that represents a message in a chat.
    """
    role: str
    content: str
