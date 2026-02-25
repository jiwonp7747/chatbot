from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class StreamStatus(str, Enum):
    PROGRESS = "progress"      # 노드별 진행 상황
    STREAMING = "streaming"     # 실제 AI 응답 chunk
    DONE = "done"              # 완료
    ERROR = "error"            # 에러
    CONFIRM = "confirm"        # HITL 도구 실행 확인 대기

class ChatRequest(BaseModel):
    chat_session_id: Optional[int]
    prompt: str
    model: Optional[str] = "gpt-5.1-mini"
    rag_tags: Optional[List[str]] = Field(default=[], description="RAG tag-scoped 검색에 사용할 태그 목록")

class ChatResponse(BaseModel):
    content: str
    status: StreamStatus
    error: Optional[str] = None
    # HITL 필드 (CONFIRM 시에만 사용)
    thread_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None

class ResumeRequest(BaseModel):
    """HITL 재개 요청"""
    thread_id: str
    approved: bool
    chat_session_id: Optional[int] = None
    model: Optional[str] = None

