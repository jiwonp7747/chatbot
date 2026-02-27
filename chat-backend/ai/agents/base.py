"""
에이전트 기본 인터페이스

모든 에이전트는 이 클래스를 상속하여 구현합니다.
오케스트레이터가 에이전트를 등록하고 as_tool()로 도구화하여 사용합니다.
"""
import logging
from abc import ABC, abstractmethod

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

from ai.agents.middleware import SubProgressMiddleware

logger = logging.getLogger("chat-server")


class BaseAgent(ABC):
    """모든 에이전트의 기본 클래스

    서브에이전트는 이 클래스를 상속하여 다음을 정의합니다:
    - get_name(): 에이전트 이름
    - get_description(): 에이전트 설명
    - get_system_prompt(): 시스템 프롬프트
    - get_tools(): 사용할 도구 목록
    - as_tool(): 메인 에이전트에서 사용할 LangChain @tool 반환
    """

    def __init__(self, model: str):
        """
        Args:
            model: create_agent용 모델 문자열 (예: "openai:gpt-4o-mini")
        """
        self.model = model
        self._graph: CompiledStateGraph | None = None

    @abstractmethod
    def get_name(self) -> str:
        """에이전트 고유 이름"""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """에이전트 설명 (오케스트레이터 라우팅 참고용)"""
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """서브에이전트의 시스템 프롬프트"""
        ...

    @abstractmethod
    def get_tools(self) -> list:
        """서브에이전트가 사용할 도구 목록"""
        ...

    @abstractmethod
    def as_tool(self):
        """서브에이전트를 메인 에이전트용 LangChain @tool로 래핑하여 반환"""
        ...

    def get_progress_label(self) -> str:
        """오케스트레이터에서 표시할 진행 메시지. 오버라이드 가능."""
        return f"⚡ {self.get_name()} 실행 중..."

    def get_middleware(self) -> list:
        """기본: SubProgressMiddleware 포함. 오버라이드하여 추가 미들웨어 가능."""
        return [SubProgressMiddleware(agent_name=self.get_name())]

    def get_checkpointer(self):
        """오버라이드하여 체크포인터 추가 (예: InMemorySaver)"""
        return None

    def build(self) -> CompiledStateGraph:
        """서브에이전트 그래프 생성 (캐싱)"""
        if self._graph is None:
            tools = self.get_tools()
            kwargs = {
                "model": self.model,
                "tools": tools if tools else None,
                "system_prompt": self.get_system_prompt(),
            }

            middleware = self.get_middleware()
            if middleware:
                kwargs["middleware"] = middleware

            checkpointer = self.get_checkpointer()
            if checkpointer:
                kwargs["checkpointer"] = checkpointer

            self._graph = create_agent(**kwargs)
            logger.info(
                f"🔨 [{self.get_name()}] 서브에이전트 빌드 완료: "
                f"도구 {len(tools) if tools else 0}개"
            )
        return self._graph

    @staticmethod
    def _content_to_str(content) -> str:
        """content가 list일 경우 텍스트만 추출하여 str로 변환"""
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
    def extract_ai_content(result: dict) -> str:
        """에이전트 실행 결과에서 마지막 AI 응답 content 추출"""
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return BaseAgent._content_to_str(msg.content)
        if messages and hasattr(messages[-1], "content"):
            return BaseAgent._content_to_str(messages[-1].content)
        return ""
