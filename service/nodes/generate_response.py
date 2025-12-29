"""
노드 3: 응답 생성

OpenAI API를 호출하여 메시지를 구성하고 스트리밍 준비를 합니다.
"""
import logging
from typing import Dict, Any

from core.config.prompt.prompt import SYSTEM_PROMPT
from schema.chat_graph_schema import ChatGraphState

logger = logging.getLogger("chat-server")


async def generate_response_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    OpenAI API 호출을 위한 메시지를 구성하는 노드

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (messages 포함)
    """
    message_history = state.get("message_history", [])
    user_prompt = state.get("user_prompt", "")
    intent_analysis = state.get("intent_analysis", {})

    # 시스템 프롬프트로 시작
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # 대화 기록 추가 (의도 분석 결과에 따라 제어 가능)
    if intent_analysis.get("requires_context", True):
        messages.extend(message_history)
    else:
        logger.info("ℹ️ 컨텍스트 불필요 - 대화 기록 제외")

    # 사용자 메시지 추가
    messages.append(
        {"role": "user", "content": user_prompt}
    )

    logger.info(f"📝 메시지 구성 완료: 총 {len(messages)}개")

    return {
        "messages": messages
    }
