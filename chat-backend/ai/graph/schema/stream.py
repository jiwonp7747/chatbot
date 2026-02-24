from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class StreamStatus(str, Enum):
    PROGRESS = "progress"      # 노드별 진행 상황
    STREAMING = "streaming"     # 실제 AI 응답 chunk
    DONE = "done"              # 완료
    ERROR = "error"            # 에러

class ChatRequest(BaseModel):
    chat_session_id: Optional[int]
    prompt: str
    model: Optional[str] = "gpt-5.1-mini"
    rag_tags: Optional[List[str]] = Field(default=[], description="RAG tag-scoped 검색에 사용할 태그 목록")

class ChatResponse(BaseModel):
    content: str
    status: StreamStatus
    error: Optional[str] = None

