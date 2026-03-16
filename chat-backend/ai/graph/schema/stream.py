from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class StreamStatus(str, Enum):
    PROGRESS = "progress"      # 노드별 진행 상황
    SUB_PROGRESS = "sub_progress"  # 서브에이전트 도구 실행 진행
    STREAMING = "streaming"     # 실제 AI 응답 chunk
    DONE = "done"              # 완료
    ERROR = "error"            # 에러
    CONFIRM = "confirm"        # HITL 도구 실행 확인 대기

class ChatRequest(BaseModel):
    thread_id: Optional[str] = None
    prompt: str
    model: Optional[str] = "gpt-5.1-mini"
    rag_tags: Optional[List[str]] = Field(default=[], description="RAG tag-scoped 검색에 사용할 태그 목록")
    checkpoint_id: Optional[str] = Field(default=None, description="Fork 시작점 checkpoint_id — 지정 시 해당 시점에서 분기")

class HitlToolCall(BaseModel):
    """HITL interrupt된 개별 도구 호출 정보"""
    name: str
    args: dict
    detail: Optional[dict] = None  # 도구별 상세 정보 (tool_name, description, args)


class AvailableTool(BaseModel):
    """HITL 수정 시 선택 가능한 도구 정보"""
    name: str
    description: str = ""

class ChatResponse(BaseModel):
    content: str
    status: StreamStatus
    error: Optional[str] = None
    # HITL 필드 (CONFIRM 시에만 사용)
    thread_id: Optional[str] = None
    tool_calls: Optional[List[HitlToolCall]] = None  # interrupt된 도구 목록
    tool_context: Optional[str] = None          # 에이전트 판단 근거 (1회, 공통)
    available_tools: Optional[List[AvailableTool]] = None  # 수정 가능한 도구 목록 (CONFIRM 시)
    # 서브에이전트 진행 상황 (SUB_PROGRESS 시에만 사용)
    agent_name: Optional[str] = None
    sub_tools: Optional[List[str]] = None
    parallel: Optional[bool] = None
    # 도구 결과 artifact (테이블 등 구조화된 데이터)
    artifact: Optional[dict] = None

class EditedToolCall(BaseModel):
    """EDIT decision용 수정된 도구 호출"""
    name: str
    args: dict

class ToolSchemaRequest(BaseModel):
    """도구 스키마 조회 요청"""
    tool_names: Optional[List[str]] = None  # None이면 전체 반환

class ResumeRequest(BaseModel):
    """HITL 재개 요청"""
    thread_id: str
    approved: bool
    model: Optional[str] = None
    edit_message: Optional[str] = None  # 거부 시 에이전트에게 전달할 메시지
    edited_tool_calls: Optional[List[EditedToolCall]] = None  # EDIT decision용


@dataclass
class StreamResult:
    """스트리밍 완료 후 결과를 전달하는 컨테이너"""
    ai_response: str = ""
    is_confirm: bool = False
    thread_id: str | None = None
    error: str | None = None

