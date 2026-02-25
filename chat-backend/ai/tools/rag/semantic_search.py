"""
Semantic Search 도구

Agent Memory 서버의 semantic search API를 LangChain Tool로 래핑합니다.
"""
import httpx
from langchain_core.tools import tool
from opentelemetry.propagate import inject

from config.telemetry import trace_tool

MEMORY_SERVER_URL = "http://localhost:6333"


@tool
async def semantic_search_tool(query: str, n_results: int = 5) -> str:
    """의미 기반으로 관련 문서를 검색합니다. 태그 없이 전체 문서에서 유사한 내용을 찾을 때 사용하세요.

    Args:
        query: 검색할 내용
        n_results: 최대 결과 수
    """
    try:
        with trace_tool("rag.semantic_search", {"search.query": query}):
            headers = {"Content-Type": "application/json"}
            inject(headers)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{MEMORY_SERVER_URL}/api/search",
                    headers=headers,
                    json={
                        "query": query,
                        "n_results": n_results,
                    },
                )
                response.raise_for_status()

            result = response.json()
            if not result.get("success"):
                return f"검색 실패: {result.get('message', 'unknown error')}"

            results = result.get("data", {}).get("results", [])
            if not results:
                return "검색 결과가 없습니다."

            formatted = []
            for idx, item in enumerate(results, 1):
                memory = item.get("memory", {})
                content = memory.get("content", "").strip()[:500]
                score = item.get("similarity_score", 0.0)
                formatted.append(f"[{idx}] (유사도: {score:.2f})\n{content}")

            return "\n\n".join(formatted)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return "시맨틱 검색 API를 사용할 수 없습니다. tag_search_tool을 대신 사용하세요."
        return f"검색 API 오류 (HTTP {e.response.status_code}). 다른 도구를 사용하세요."

    except httpx.ConnectError:
        return "Memory 서버에 연결할 수 없습니다. 검색 없이 답변을 생성하세요."

    except Exception as e:
        return f"검색을 사용할 수 없습니다. 검색 없이 답변을 생성하세요."
