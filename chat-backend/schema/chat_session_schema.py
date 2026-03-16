from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any

class ChatSessionResponse(BaseModel):
    thread_id: str
    session_title: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ChatSessionTitleUpdateRequest(BaseModel):
    session_title: str

class ChatMessageResponse(BaseModel):
    id: str
    role: str  # "user" | "assistant" | "tool"
    content: str
    created_at: Optional[datetime] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    data_ref_type: Optional[str] = None  # "artifact" | "file" | None


class ToolResultResponse(BaseModel):
    tool_call_id: str
    tool_name: Optional[str] = None
    data_ref_type: Optional[str] = None
    data: Any = None
