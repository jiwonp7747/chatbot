from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime


class ChatGraphState(TypedDict):
    """LangGraph State 정의

    각 노드에서 공유하는 상태 정보
    """
    # 입력 데이터
    chat_session_id: Optional[int]
    user_prompt: str
    model: str

    # 대화 기록
    message_history: List[Dict[str, str]]  # [{"role": "user", "content": "..."}, ...]

    # 의도 분석 결과
    intent_analysis: Optional[Dict[str, Any]]  # {"intent": "question", "confidence": 0.9, ...}

    # OpenAI 메시지 구성
    messages: List[Dict[str, str]]

    # 응답 생성
    ai_response: str  # 전체 응답 내용

    # 메타데이터
    user_chat_created_at: datetime
    stream_id: Optional[str]

    # 에러 처리
    error: Optional[str]
