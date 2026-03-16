from pydantic import BaseModel
from datetime import datetime
from typing import Optional

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
    role: str
    content: str
    created_at: Optional[datetime] = None
