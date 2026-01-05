"""
노드 4: 응답 생성

OpenAI API를 호출하여 메시지를 구성하고, 추가 도구 필요 여부를 판단합니다.
"""
import logging
import json
from typing import Dict, Any

from client.openai_client import aclient
from core.config.prompt.prompt import SYSTEM_PROMPT
from schema.chat_graph_schema import ChatGraphState

logger = logging.getLogger("chat-server")

# 추가 도구 필요 여부 판단을 위한 프롬프트
TOOL_DECISION_PROMPT = """도구 실행 결과를 바탕으로 사용자의 요청에 완전히 답변할 수 있는지 판단하세요.

추가 도구가 필요한 경우 다음 JSON 형식으로 응답하세요:
{
    "needs_more_tools": true,
    "tools": [
        {
            "name": "도구_이름",
            "arguments": {...},
            "reason": "필요한 이유"
        }
    ],
    "reasoning": "추가 도구가 필요한 이유"
}

추가 도구가 필요 없으면:
{
    "needs_more_tools": false,
    "tools": [],
    "reasoning": "현재 정보로 충분히 답변 가능"
}

**주의**: 
- JSON 데이터 외에 어떤 설명이나 텍스트도 출력하지 마세요. 
- 마크다운 코드 블록(```)도 사용하지 말고 순수 JSON 문자열만 출력하세요.
"""


async def generate_response_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    OpenAI API 호출을 위한 메시지를 구성하고, 추가 도구 필요 여부를 판단하는 노드

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (messages, needs_more_tools, tools_to_call 포함)
    """
    message_history = state.get("message_history", [])
    user_prompt = state.get("user_prompt", "")
    intent_analysis = state.get("intent_analysis", {})
    tool_results = state.get("tool_results", [])
    iteration_count = state.get("iteration_count", 0)
    model = state.get("model", "gpt-5.1-mini")

    # 시스템 프롬프트로 시작
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # 대화 기록 추가 (의도 분석 결과에 따라 제어 가능)
    if intent_analysis.get("requires_context", True):
        messages.extend(message_history)
    else:
        logger.info("ℹ️ 컨텍스트 불필요 - 대화 기록 제외")

    # 도구 실행 결과가 있으면 컨텍스트에 포함
    if tool_results:
        tool_context = _format_tool_results(tool_results)
        messages.append({
            "role": "system",
            "content": f"다음은 도구 실행 결과입니다:\n\n{tool_context}"
        })
        logger.info(f"🔧 도구 실행 결과 {len(tool_results)}개 포함")

    # 사용자 메시지 추가
    messages.append(
        {"role": "user", "content": user_prompt}
    )

    logger.info(f"📝 메시지 구성 완료: 총 {len(messages)}개")

    # 추가 도구 필요 여부 판단 (최대 반복 횟수 체크)
    needs_more_tools = False
    new_tools_to_call = []

    if iteration_count < 5 and tool_results:  # 최대 5회 반복
        try:
            logger.info("🤔 추가 도구 필요 여부 판단 중...")

            # gpt-5.1-mini는 temperature 커스텀 값을 지원하지 않으므로 제거
            decision_response = await aclient.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": TOOL_DECISION_PROMPT},
                    {"role": "user", "content": f"사용자 요청: {user_prompt}\n\n도구 실행 결과: {json.dumps(tool_results, ensure_ascii=False)}"}
                ]
            )

            decision_text = decision_response.choices[0].message.content
            logger.info(f"📄 도구 판단 결과: {decision_text}")

            decision = json.loads(decision_text)
            needs_more_tools = decision.get("needs_more_tools", False)
            new_tools_to_call = decision.get("tools", [])

            if needs_more_tools:
                logger.info(f"🔄 추가 도구 필요: {len(new_tools_to_call)}개")
            else:
                logger.info("✅ 추가 도구 불필요 - 응답 생성 준비 완료")

        except Exception as e:
            logger.error(f"❌ 도구 판단 실패: {e}")
            needs_more_tools = False

    return {
        "messages": messages,
        "needs_more_tools": needs_more_tools,
        "tools_to_call": new_tools_to_call,
        "iteration_count": iteration_count + 1
    }


def _format_tool_results(tool_results: list) -> str:
    """
    도구 실행 결과를 사람이 읽을 수 있는 형식으로 포맷팅

    Args:
        tool_results: 도구 실행 결과 리스트

    Returns:
        포맷팅된 문자열
    """
    formatted = []

    for idx, result in enumerate(tool_results, 1):
        tool_name = result.get("tool", "unknown")
        success = result.get("success", False)

        if success:
            result_data = result.get("result", {})
            content_items = result_data.get("content", [])

            formatted.append(f"[도구 {idx}: {tool_name}] ✅ 성공")

            for item in content_items:
                item_type = item.get("type")
                if item_type == "text":
                    formatted.append(f"  내용: {item.get('text', '')}")
                elif item_type == "image":
                    formatted.append(f"  이미지: {item.get('mimeType', 'image/png')}")
                elif item_type == "resource":
                    formatted.append(f"  리소스: {item.get('uri', '')}")
        else:
            error = result.get("error", "Unknown error")
            formatted.append(f"[도구 {idx}: {tool_name}] ❌ 실패: {error}")

    return "\n".join(formatted)
