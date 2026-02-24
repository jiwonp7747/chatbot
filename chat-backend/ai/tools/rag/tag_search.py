"""
Tag-Scoped Search 도구

Agent Memory 서버의 tag-scoped search API를 LangChain Tool로 래핑합니다.
"""
import httpx
from langchain_core.tools import tool

MEMORY_SERVER_URL = "http://localhost:6333"


@tool
async def tag_search_tool(query: str, tags: list[str], n_results: int = 5) -> str:
    """태그 기반으로 관련 문서를 검색합니다. 업로드된 문서에서 특정 카테고리의 정보를 찾을 때 사용하세요.

    Args:
        query: 검색할 내용
        tags: 필터링할 태그 목록 (예: ["file_type:pdf", "ncs/정보기술관리"])
        n_results: 최대 결과 수
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MEMORY_SERVER_URL}/api/search/tag-scoped",
                json={
                    "query": query,
                    "tags": tags,
                    "n_results": n_results,
                    "tag_operation": "OR",
                    "include_descendants": True,
                    "similarity_threshold": 0.3,
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
            content = item.get("content", "").strip()[:500]
            similarity = item.get("similarity", 0.0)
            formatted.append(f"[{idx}] (유사도: {similarity:.2f})\n{content}")

        return "\n\n".join(formatted)

    except Exception as e:
        return f"검색 중 오류 발생: {str(e)}"
