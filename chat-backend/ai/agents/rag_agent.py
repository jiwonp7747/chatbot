"""
RAG 검색 전문 서브에이전트

업로드된 문서에서 태그 기반 + 시맨틱 검색을 수행합니다.
as_tool()로 메인 에이전트의 도구로 사용됩니다.
"""
import logging

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from ai.agents.base import BaseAgent
from ai.tools.rag import get_rag_tools

logger = logging.getLogger("chat-server")

RAG_AGENT_PROMPT = """당신은 문서 검색 전문가입니다.
사용자의 질문에 관련된 문서를 정확하게 찾아 핵심 내용을 정리하세요.

도구 사용 가이드:
- 태그가 지정된 경우 → tag_search_tool 사용
- 태그 없이 일반 검색 → semantic_search_tool 사용
- 필요하면 두 도구를 순서대로 사용하여 더 정확한 결과를 얻으세요.

검색 결과를 그대로 나열하지 말고, 사용자 질문에 맞게 요약하여 답변하세요.
"""


class RagAgent(BaseAgent):

    def get_name(self) -> str:
        return "rag_agent"

    def get_description(self) -> str:
        return "업로드된 문서에서 정보를 검색하고 관련 내용을 찾습니다"

    def get_system_prompt(self) -> str:
        return RAG_AGENT_PROMPT

    def get_tools(self) -> list:
        return get_rag_tools()

    def as_tool(self):
        """RAG 서브에이전트를 search_documents 도구로 래핑"""
        agent = self.build()

        @tool
        async def search_documents(query: str, tags: str = "") -> str:
            """업로드된 문서에서 정보를 검색합니다. 문서 관련 질문이나 자료 검색이 필요할 때 사용하세요.

            Args:
                query: 검색할 질문이나 키워드
                tags: 쉼표로 구분된 태그 목록 (예: "file_type:pdf,ncs/정보기술"). 없으면 전체 검색
            """
            prompt = query
            if tags:
                prompt += f"\n\n[다음 태그로 검색하세요: {tags}]"

            logger.info(f"📖 RAG 서브에이전트 호출: query={query[:50]}, tags={tags}")
            result = await agent.ainvoke({
                "messages": [HumanMessage(content=prompt)]
            })
            return self.extract_ai_content(result)

        return search_documents
