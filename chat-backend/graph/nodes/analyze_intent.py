"""
노드 2: 의도 분석

사용자의 의도를 분석하고 필요한 MCP 도구를 파악합니다.
- 질문 유형 분류 (일반 질문, 코드 작성, 번역 등)
- 컨텍스트 필요 여부 판단
- 필요한 MCP 도구 식별
"""
import logging
import json
from typing import Dict, Any

from client.openai_client import aclient
from graph.schema.graph_state import ChatGraphState

logger = logging.getLogger("chat-server")

# 도구 분석 및 인증 정보 주입을 위한 시스템 프롬프트
TOOL_ANALYSIS_PROMPT_BASE = """당신은 사용자의 요청을 분석하여 필요한 도구를 파악하는 AI 어시스턴트입니다.

[인증 정보]
본 시스템은 도구 호출 시 다음의 인증 토큰을 사용해야 합니다:
- Auth Token: {token}

사용자의 요청을 분석하여 다음을 결정하세요:
1. 의도 분류 (general_chat, translation, code_generation, question, data_visualization, calculation 등)
2. 필요한 도구 목록 (있다면)

응답은 반드시 다음 JSON 형식으로만 제공하세요:
{{
    "intent": "의도 분류",
    "confidence": 0.0-1.0,
    "requires_context": true/false,
    "tools": [
        {{
            "name": "도구_이름",
            "arguments": {{
                "token": "{token}",
                "args1": "value1"
            }},
            "reason": "도구가 필요한 이유"
        }}
    ]
}}

도구가 필요 없으면 "tools": [] 로 응답하세요.

**주의**: 
- JSON 데이터 외에 어떤 설명이나 텍스트도 출력하지 마세요. 
- 마크다운 코드 블록(```)도 사용하지 말고 순수 JSON 문자열만 출력하세요.
"""


def _build_tool_analysis_prompt(token:str, available_tools: list) -> str:
    """
    사용 가능한 도구 목록을 포함한 프롬프트 생성

    Args:
        available_tools: 사용 가능한 도구 목록

    Returns:
        도구 목록이 포함된 프롬프트
    """
    tool_analysis_prompt = TOOL_ANALYSIS_PROMPT_BASE.format(token=token)
    if not available_tools:
        return tool_analysis_prompt

    # 도구 목록을 문자열로 포맷팅
    tools_description = "\n\n**사용 가능한 도구 목록:**\n"
    for tool in available_tools:
        tools_description += f"\n- **{tool['name']}**: {tool['description']}\n"
        if tool.get('inputSchema'):
            schema = tool['inputSchema']
            if 'properties' in schema:
                tools_description += f"  파라미터: {', '.join(schema['properties'].keys())}\n"

    tools_description += ("\n**중요**: 위 목록에 있는 도구만 사용할 수 있습니다. 목록에 없는 도구는 사용하지 마세요."
                          "\n 목록에 없는 도구는 절대 호출하지 않되 만약 호출하게 되는 경우 reason에다가 목록에 없는 도구 호출이라는 메시지를 넣으세요")

    return tool_analysis_prompt + tools_description


def _build_response_schema(available_tools: list) -> dict:
    """
    사용 가능한 도구를 기반으로 JSON Schema 생성 (Structured Outputs용)

    ✅ 핵심: 도구 이름을 enum으로 제한하여 AI가 목록에 없는 도구를 선택할 수 없게 함

    Args:
        available_tools: 사용 가능한 도구 목록

    Returns:
        OpenAI response_format용 JSON Schema
    """
    # 도구 이름 목록 추출
    tool_names = [tool['name'] for tool in available_tools] if available_tools else []

    # 도구가 없을 경우 enum 없이 처리
    if not tool_names:
        tool_name_schema = {"type": "string", "description": "사용할 도구 이름"}
    else:
        tool_name_schema = {
            "type": "string",
            "enum": tool_names,  # ✅ 이게 핵심! 목록에 없는 이름은 생성 불가
            "description": "사용할 도구 이름 (반드시 목록에 있는 것만)"
        }

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "intent_analysis",
            "strict": False,  # ✅ strict 모드 비활성화 (arguments의 유연성 위해)
            "schema": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": "의도 분류"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "신뢰도 (0.0-1.0)"
                    },
                    "requires_context": {
                        "type": "boolean",
                        "description": "컨텍스트 필요 여부"
                    },
                    "tools": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": tool_name_schema,  # ✅ enum 제약은 여전히 유효!
                                "arguments": {
                                    "type": "object",
                                    "description": "도구 호출에 필요한 인자"
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "도구가 필요한 이유"
                                }
                            },
                            "required": ["name", "arguments", "reason"]
                        },
                        "description": "필요한 도구 목록"
                    }
                },
                "required": ["intent", "confidence", "requires_context", "tools"]
            }
        }
    }


async def analyze_intent_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    사용자 의도를 분석하고 필요한 도구를 파악하는 노드

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (intent_analysis, tools_to_call 포함)
    """
    user_prompt = state.get("user_prompt", "")
    model = state.get("model", "gpt-5.1-mini")
    available_tools = state.get("available_tools", [])
    token = state.get("token")

    logger.info(f"🎯 의도 분석 시작: {user_prompt[:50]}...")

    try:
        # 도구 목록을 포함한 프롬프트 생성
        tool_analysis_prompt = _build_tool_analysis_prompt(token, available_tools)

        logger.info(f"도구 분석 프롬프트: {tool_analysis_prompt}")

        # ✅ JSON Schema 생성 (도구 이름을 enum으로 제한)
        response_schema = _build_response_schema(available_tools)
        logger.info(f"📐 Response Schema: {response_schema}")

        # OpenAI API를 통한 의도 분석 (Structured Outputs 사용)
        response = await aclient.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": tool_analysis_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=response_schema  # ✅ 핵심: 스키마 강제 적용
        )

        logger.info(f"📄 response 원본: {response}")

        analysis_text = response.choices[0].message.content

        # JSON 파싱
        analysis = json.loads(analysis_text)

        intent_analysis = {
            "intent": analysis.get("intent", "general_chat"),
            "confidence": analysis.get("confidence", 1.0),
            "requires_context": analysis.get("requires_context", True),
            "prompt_length": len(user_prompt),
        }

        tools_to_call = analysis.get("tools", [])

        logger.info(f"✅ 의도 분석 완료: {intent_analysis['intent']}, 도구: {len(tools_to_call)}개")

        return {
            "intent_analysis": intent_analysis,
            "tools_to_call": tools_to_call
        }

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 파싱 실패: {e}")
        # 파싱 실패 시 기본값 사용
        return {
            "intent_analysis": {
                "intent": "general_chat",
                "confidence": 0.5,
                "requires_context": True,
                "prompt_length": len(user_prompt),
            },
            "tools_to_call": []
        }

    except Exception as e:
        logger.error(f"❌ 의도 분석 실패: {e}")
        return {
            "intent_analysis": {
                "intent": "general_chat",
                "confidence": 0.0,
                "requires_context": True,
                "prompt_length": len(user_prompt),
            },
            "tools_to_call": [],
            "error": f"Intent analysis failed: {str(e)}"
        }
