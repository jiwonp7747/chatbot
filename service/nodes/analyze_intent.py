"""
노드 2: 의도 분석

사용자의 의도를 분석합니다. (현재는 기본 구현, 추후 확장 가능)
향후 확장 가능한 기능:
- 질문 유형 분류 (일반 질문, 코드 작성, 번역 등)
- 컨텍스트 필요 여부 판단
- 특수 처리가 필요한 요청 감지
"""
import logging
from typing import Dict, Any

from schema.chat_graph_schema import ChatGraphState

logger = logging.getLogger("chat-server")


async def analyze_intent_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    사용자 의도를 분석하는 노드

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (intent_analysis 포함)
    """
    user_prompt = state.get("user_prompt", "")

    # 기본 의도 분석 (추후 LLM 기반으로 확장 가능)
    intent_analysis = {
        "intent": "general_chat",  # 기본값
        "confidence": 1.0,
        "requires_context": True,  # 대화 기록 필요 여부
        "prompt_length": len(user_prompt),
    }

    # 간단한 규칙 기반 분석 (추후 확장)
    if any(keyword in user_prompt.lower() for keyword in ["번역", "translate"]):
        intent_analysis["intent"] = "translation"
    elif any(keyword in user_prompt.lower() for keyword in ["코드", "code", "프로그램"]):
        intent_analysis["intent"] = "code_generation"
    elif "?" in user_prompt or any(keyword in user_prompt for keyword in ["무엇", "어떻게", "왜"]):
        intent_analysis["intent"] = "question"

    logger.info(f"🎯 의도 분석 완료: {intent_analysis['intent']}")

    return {
        "intent_analysis": intent_analysis
    }
