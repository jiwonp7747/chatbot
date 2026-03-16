"""LangGraph Runtime Context 스키마

State가 아닌 Runtime Context로 관리되는 요청 환경값을 정의합니다.
노드/도구에서 runtime.context.* 로 접근합니다.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChatContext:
    """채팅 요청의 런타임 컨텍스트"""
    thread_id: Optional[str] = None
    token: Optional[str] = None
