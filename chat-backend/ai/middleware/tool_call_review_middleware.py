"""도구 호출 리뷰 미들웨어

LLM 응답의 content(텍스트)와 실제 tool_calls를 비교하여
도구 호출 의도와 실제 행동이 일치하는지 검토합니다.

검증 흐름:
  1. 메인 LLM 응답 (content + tool_calls) 수신
  2. 별도 경량 LLM으로 content를 분석 → 도구 호출 의도 추출
  3. 의도와 실제 tool_calls 비교
  4. 불일치 시 프롬프트 보강 후 재시도
"""
import logging
from typing import Awaitable, Callable

from langchain.agents.middleware import (
    AgentMiddleware,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
)
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.typing import ContextT
from pydantic import BaseModel

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM_PROMPT = """\
당신은 AI 응답 분석기입니다.
AI 어시스턴트의 응답 텍스트를 분석하여, 도구나 에이전트를 호출하겠다는 의도가 있는지 판단하세요.

## 판단 기준

"의도 있음"으로 판단하는 경우:
- "~를 실행하겠습니다", "~를 호출하겠습니다", "~에게 위임하겠습니다"
- "~를 분석하겠습니다", "~를 검색하겠습니다" (도구 사용을 암시)
- "~를 확인해보겠습니다" (도구를 통한 확인을 암시)

"의도 없음"으로 판단하는 경우:
- 직접 답변만 제공하는 경우
- 단순 인사, 대화, 질문인 경우
- 이미 도구 결과를 요약하여 보여주는 경우"""

VERIFIER_USER_PROMPT = """\
다음 AI 응답을 분석하세요.

## AI 응답 텍스트
{content}

## 사용 가능한 도구 목록
{available_tools}"""


class ToolCallIntent(BaseModel):
    """검증 LLM의 구조화된 응답"""

    has_tool_intent: bool
    """도구/에이전트 호출 의도가 있는지 여부"""
    intended_tools: list[str]
    """호출하려는 것으로 보이는 도구/에이전트 이름 목록"""
    reason: str
    """판단 근거"""


class ToolCallReviewMiddleware(AgentMiddleware):
    """LLM 응답의 도구 호출 의도와 실제 행동을 검토하는 미들웨어

    별도 경량 LLM으로 content의 도구 호출 의도를 분석하고,
    실제 tool_calls와 비교하여 불일치 시 재시도합니다.

    Args:
        verifier_model: 검증용 LLM 모델명
        max_retries: 불일치 감지 시 최대 재시도 횟수
    """

    def __init__(self, verifier_model: str, max_retries: int = 1 ):
        self.max_retries = max_retries
        self.verifier_model = verifier_model

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[
            [ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]
        ],
    ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
        available_tool_names = [
            t.name if hasattr(t, "name") else str(t) for t in request.tools
        ]

        for attempt in range(self.max_retries + 1):
            response = await handler(request)
            ai_msg = self._extract_ai_message(response)
            if ai_msg is None:
                return response

            content = self._get_content_str(ai_msg)
            actual_tool_calls = ai_msg.tool_calls or []

            # 도구 호출이 있으면 정상
            if actual_tool_calls:
                return response

            # content가 비어있으면 검증 불필요
            if not content.strip():
                return response

            # 검증 LLM으로 도구 호출 의도 분석
            intent = await self._verify_intent(content, available_tool_names)

            if not intent.has_tool_intent:
                # 도구 호출 의도 없음 → 정상 직접 답변
                return response

            # 할루시네이션 감지: 의도는 있는데 실제 호출 없음
            logger.warning(
                f"🚨 도구 호출 할루시네이션 감지 (시도 {attempt + 1}/{self.max_retries + 1}): "
                f"의도={intent.intended_tools}, 실제 tool_calls=[], "
                f"근거={intent.reason}"
            )

            if attempt < self.max_retries:
                tools_str = ", ".join(intent.intended_tools)
                reinforcement = (
                    f"\n\n[필수 지침] 사용자의 요청에 '{tools_str}' 도구 호출이 필요합니다. "
                    f"(근거: {intent.reason})\n"
                    f"반드시 tool_calls에 해당 도구를 포함하여 응답하세요. "
                    f"텍스트로 '호출하겠습니다'라고만 작성하는 것은 실제 호출이 아닙니다. "
                    f"도구를 호출할 수 없는 상황이라면, 사용자에게 그 이유를 솔직하게 설명하세요."
                )
                current_system = request.system_message
                if current_system:
                    new_system = SystemMessage(
                        content=current_system.text + reinforcement
                    )
                    request = request.override(system_message=new_system)

                logger.info(
                    f"🔄 프롬프트 보강 후 재시도 ({attempt + 1}/{self.max_retries})"
                )

        logger.warning("⚠️ 할루시네이션 재시도 한도 초과, 마지막 응답 반환")
        return response

    async def _verify_intent(
        self, content: str, available_tools: list[str]
    ) -> ToolCallIntent:
        """별도 경량 LLM으로 content의 도구 호출 의도를 분석"""
        from langchain.chat_models import init_chat_model

        tools_str = ", ".join(available_tools) if available_tools else "(없음)"

        try:
            llm = init_chat_model(self.verifier_model).with_structured_output(
                ToolCallIntent
            )
            result = await llm.ainvoke([
                SystemMessage(content=VERIFIER_SYSTEM_PROMPT),
                {"role": "user", "content": VERIFIER_USER_PROMPT.format(
                    content=content[:2000],
                    available_tools=tools_str,
                )},
            ])
            parsed: ToolCallIntent = result  # type: ignore[assignment]
            logger.debug(
                f"🔍 검증 LLM 결과: intent={parsed.has_tool_intent}, "
                f"tools={parsed.intended_tools}, reason={parsed.reason}"
            )
            return parsed

        except Exception as e:
            logger.warning(f"⚠️ 검증 LLM 호출 실패 (통과 처리): {e}")
            return ToolCallIntent(
                has_tool_intent=False,
                intended_tools=[],
                reason=f"검증 LLM 호출 실패: {e}",
            )

    @staticmethod
    def _extract_ai_message(response: ModelResponse) -> AIMessage | None:
        """ModelResponse에서 AIMessage를 추출"""
        if isinstance(response, AIMessage):
            return response
        if hasattr(response, "result") and response.result:
            for msg in response.result:
                if isinstance(msg, AIMessage):
                    return msg
        return None

    @staticmethod
    def _get_content_str(msg: AIMessage) -> str:
        """AIMessage content를 문자열로 변환"""
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and part.get("type") == "text":
                    parts.append(part.get("text", ""))
            return "".join(parts)
        return str(content) if content else ""


def create_tool_call_review_middleware(
    verifier_model: str,
    max_retries: int = 1,
) -> ToolCallReviewMiddleware:
    """ToolCallReviewMiddleware 팩토리 함수"""
    return ToolCallReviewMiddleware(
        max_retries=max_retries,
        verifier_model=verifier_model,
    )