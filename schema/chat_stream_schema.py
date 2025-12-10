from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class StreamStatus(str, Enum):
    STREAMING = "streaming"
    DONE = "done"
    ERROR = "error"

class ChatRequest(BaseModel):
    prompt: str
    model: Optional[str] = "gpt-5.1-mini"

class ChatResponse(BaseModel):
    content: str
    status: StreamStatus
    error: Optional[str] = None

