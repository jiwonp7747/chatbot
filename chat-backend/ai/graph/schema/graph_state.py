from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime


class ChatGraphState(TypedDict, total=False):
    """LangGraph State 정의

    각 노드에서 공유하는 상태 정보
    total=False: 모든 필드가 optional임을 명시
    """
    # 입력 데이터
    chat_session_id: Optional[int]
    user_prompt: str
    model: str  # model key
    api_model: str
    provider: str

    # 대화 기록
    message_history: List[Dict[str, str]]  # [{"role": "user", "content": "..."}, ...]

    # 의도 분석 결과
    intent_analysis: Optional[Dict[str, Any]]  # {"intent": "question", "confidence": 0.9, ...}

    # MCP 도구 호출 관련
    available_tools: List[Dict[str, Any]]  # MCP 서버에서 사용 가능한 도구 목록
    tools_to_call: List[Dict[str, Any]]  # [{"name": "tool_name", "arguments": {...}}, ...]
    tool_results: List[Dict[str, Any]]  # [{"tool": "tool_name", "result": {...}}, ...]
    needs_more_tools: bool  # 추가 도구 호출 필요 여부
    iteration_count: int  # 반복 횟수 (무한 루프 방지)

    # OpenAI 메시지 구성
    messages: List[Dict[str, str]]

    # RAG 검색 관련
    rag_tags: List[str]  # tag-scoped search에 사용할 태그 목록
    rag_results: List[Dict[str, Any]]  # RAG 검색 결과

    # 응답 생성
    ai_response: str  # 전체 응답 내용

    # 메타데이터
    user_chat_created_at: datetime
    stream_id: Optional[str]

    # 에러 처리
    error: Optional[str]

    # 인증 데이터
    token: str
