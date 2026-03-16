"""도구 호출 주입 미들웨어

LLM이 도구를 호출하겠다고 했지만 실제 tool_calls가 비어있을 때,
별도 LLM이 적절한 tool_call을 판단하여 AIMessage에 직접 주입합니다.

Review 미들웨어와 달리 재시도 없이, 응답을 수정하여 즉시 반환합니다.

검증 흐름:
  1. 메인 LLM 응답 (content + tool_calls) 수신
  2. tool_calls 비어있고 content에 위임 의도가 있으면
  3. 별도 LLM으로 적절한 tool_call (subagent_type, description) 결정
  4. AIMessage.tool_calls에 주입하여 반환
"""
import logging
import uuid
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

INJECTOR_SYSTEM_PROMPT = """\
당신은 AI 오케스트레이터의 도구 호출 보정기입니다.
AI 어시스턴트가 도구를 호출하려 했지만 실제로 호출하지 못한 경우,
적절한 도구 호출 정보를 생성합니다.

## 규칙
1. AI 응답 텍스트와 사용 가능한 도구/에이전트 목록을 분석하세요.
2. 도구 호출 의도가 있다면, 가장 적합한 도구와 인자를 결정하세요.
3. 도구 호출 의도가 없다면, should_inject를 false로 설정하세요.
4. description은 사용자의 원래 요청을 충실히 반영하여 상세하게 작성하세요."""

INJECTOR_USER_PROMPT = """\
## AI 응답 텍스트
{content}

## 사용자 원래 요청
{user_message}

## 사용 가능한 에이전트 목록
{available_agents}"""


class ToolCallInjection(BaseModel):
    """주입할 tool_call 정보"""

    should_inject: bool
    """도구 호출을 주입해야 하는지 여부"""
    subagent_type: str
    """호출할 서브에이전트 타입 (예: analyze-fab-trace, search-documents)"""
    description: str
    """서브에이전트에게 전달할 작업 설명"""
    reason: str
    """판단 근거"""


class ToolCallInjectMiddleware(AgentMiddleware):
    """도구 호출이 누락된 경우 직접 주입하는 미들웨어

    LLM 응답에 도구 호출 의도가 있지만 tool_calls가 비어있을 때,
    별도 LLM이 적절한 tool_call을 결정하여 AIMessage에 주입합니다.

    Args:
        injector_model: 주입 결정용 LLM 모델명
    """

    def __init__(self, injector_model: str):
        self.injector_model = injector_model

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[
            [ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]
        ],
    ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
        response = await handler(request)
        ai_msg = self._extract_ai_message(response)
        if ai_msg is None:
            return response

        # 이미 tool_calls가 있으면 정상 통과
        if ai_msg.tool_calls:
            return response

        content = self._get_content_str(ai_msg)
        if not content.strip():
            return response

        # 사용자 메시지 추출 (마지막 HumanMessage)
        user_message = self._extract_last_user_message(request.messages)

        # 사용 가능한 에이전트 정보 추출 (task 도구의 description에서)
        available_agents = self._extract_available_agents(request.tools)

        # 주입 LLM으로 적절한 tool_call 결정
        injection = await self._determine_injection(
            content, user_message, available_agents
        )

        if not injection.should_inject:
            return response

        # tool_call 주입
        tool_call_id = f"call_{uuid.uuid4().hex[:24]}"
        injected_tool_call = {
            "name": "task",
            "args": {
                "subagent_type": injection.subagent_type,
                "description": injection.description,
            },
            "id": tool_call_id,
            "type": "tool_call",
        }

        # AIMessage에 tool_calls 주입
        modified_msg = AIMessage(
            content=content,
            tool_calls=[injected_tool_call],
            id=ai_msg.id,
        )

        logger.warning(
            f"💉 도구 호출 주입: subagent={injection.subagent_type}, "
            f"근거={injection.reason}"
        )

        # ModelResponse의 result에서 원본 AIMessage를 교체
        return self._replace_ai_message(response, modified_msg)

    async def _determine_injection(
        self,
        content: str,
        user_message: str,
        available_agents: str,
    ) -> ToolCallInjection:
        """별도 LLM으로 주입할 tool_call 정보를 결정"""
        from langchain.chat_models import init_chat_model

        try:
            llm = init_chat_model(self.injector_model).with_structured_output(
                ToolCallInjection
            )
            result = await llm.ainvoke([
                SystemMessage(content=INJECTOR_SYSTEM_PROMPT),
                {
                    "role": "user",
                    "content": INJECTOR_USER_PROMPT.format(
                        content=content[:2000],
                        user_message=user_message[:1000],
                        available_agents=available_agents,
                    ),
                },
            ])
            parsed: ToolCallInjection = result  # type: ignore[assignment]
            logger.info(
                f"🔍 주입 LLM 결과: inject={parsed.should_inject}, "
                f"agent={parsed.subagent_type}, reason={parsed.reason}"
            )
            return parsed

        except Exception as e:
            logger.warning(f"⚠️ 주입 LLM 호출 실패 (통과 처리): {e}")
            return ToolCallInjection(
                should_inject=False,
                subagent_type="",
                description="",
                reason=f"주입 LLM 호출 실패: {e}",
            )

    @staticmethod
    def _extract_last_user_message(messages: list) -> str:
        """메시지 목록에서 마지막 사용자 메시지 추출"""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                content = msg.content
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    return " ".join(
                        p.get("text", "") if isinstance(p, dict) else str(p)
                        for p in content
                    )
        return ""

    @staticmethod
    def _extract_available_agents(tools: list) -> str:
        """request.tools에서 task 도구의 서브에이전트 정보 추출"""
        for t in tools:
            name = t.name if hasattr(t, "name") else ""
            if name == "task":
                desc = getattr(t, "description", "")
                # "Available agent types" 이후의 에이전트 목록 추출
                marker = "Available agent types and the tools they have access to:"
                if marker in desc:
                    return desc[desc.index(marker) + len(marker):].split("When using")[0].strip()
                # 대안: 전체 description 반환
                return desc[:2000]
        return "(없음)"

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

    @staticmethod
    def _replace_ai_message(
        response: ModelResponse, new_msg: AIMessage
    ) -> ModelResponse:
        """ModelResponse의 AIMessage를 교체"""
        if isinstance(response, AIMessage):
            return new_msg  # type: ignore[return-value]
        if hasattr(response, "result"):
            new_result = [
                new_msg if isinstance(msg, AIMessage) else msg
                for msg in response.result
            ]
            return ModelResponse(
                result=new_result,
                structured_response=response.structured_response,
            )
        return response


def create_tool_call_inject_middleware(
    injector_model: str,
) -> ToolCallInjectMiddleware:
    """ToolCallInjectMiddleware 팩토리 함수"""
    return ToolCallInjectMiddleware(injector_model=injector_model)