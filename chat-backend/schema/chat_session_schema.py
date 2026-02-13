from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class ChatMessageCreateRequest(BaseModel):
    session_id: Optional[int] = None
    message: str

class ChatSessionResponse(BaseModel):
    session_title: Optional[str] = None
    chat_session_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ChatSessionTitleUpdateRequest(BaseModel):
    session_title: str

class ChatMessageResponse(BaseModel):
    chat_message_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
