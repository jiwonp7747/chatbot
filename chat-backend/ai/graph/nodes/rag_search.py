"""
노드: RAG 검색 (Tag-Scoped Search)

Agent Memory 서버의 tag-scoped search API를 호출하여
태그 필터링 + 시맨틱 검색을 수행합니다.
"""
import logging
from typing import Dict, Any

import httpx

from ai.graph.schema.graph_state import ChatGraphState

logger = logging.getLogger("chat-server")

# Agent Memory 서버 기본 URL
MEMORY_SERVER_BASE_URL = "http://localhost:6333"
RAG_SEARCH_ENDPOINT = f"{MEMORY_SERVER_BASE_URL}/api/search/tag-scoped"

# 기본 검색 설정
DEFAULT_N_RESULTS = 5
DEFAULT_TAG_OPERATION = "OR"
DEFAULT_INCLUDE_DESCENDANTS = True
DEFAULT_SIMILARITY_THRESHOLD = 0.3


async def rag_search_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    Agent Memory 서버의 tag-scoped search API를 호출하는 RAG 검색 노드

    - rag_tags가 비어있으면 검색을 건너뜁니다.
    - user_prompt를 query로 사용하여 시맨틱 검색을 수행합니다.

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (rag_results 포함)
    """
    rag_tags = state.get("rag_tags", [])
    user_prompt = state.get("user_prompt", "")

    # 태그가 없으면 RAG 검색 건너뛰기
    if not rag_tags:
        logger.info("ℹ️ RAG 태그가 없어 검색을 건너뜁니다")
        return {"rag_results": []}

    logger.info(f"🔍 RAG 검색 시작: query='{user_prompt[:50]}...', tags={rag_tags}")

    try:
        request_body = {
            "query": user_prompt,
            "tags": rag_tags,
            "n_results": DEFAULT_N_RESULTS,
            "tag_operation": DEFAULT_TAG_OPERATION,
            "include_descendants": DEFAULT_INCLUDE_DESCENDANTS,
            "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                RAG_SEARCH_ENDPOINT,
                json=request_body,
            )
            response.raise_for_status()

        result = response.json()

        if not result.get("success"):
            logger.warning(f"⚠️ RAG 검색 실패 응답: {result.get('message')}")
            return {"rag_results": []}

        data = result.get("data", {})
        results = data.get("results", [])
        total_found = data.get("total_found", 0)
        processing_time = data.get("processing_time_ms", 0)

        logger.info(
            f"✅ RAG 검색 완료: {total_found}건 발견, "
            f"{len(results)}건 반환 ({processing_time:.1f}ms)"
        )

        # 검색 결과에서 필요한 정보만 추출
        rag_results = []
        for item in results:
            rag_results.append({
                "content": item.get("content", ""),
                "tags": item.get("tags", []),
                "memory_type": item.get("memory_type", ""),
                "similarity": item.get("similarity", 0.0),
                "metadata": item.get("metadata", {}),
            })

        return {"rag_results": rag_results}

    except httpx.HTTPStatusError as e:
        logger.error(f"❌ RAG 검색 HTTP 에러: {e.response.status_code} - {e.response.text}")
        return {"rag_results": []}

    except httpx.ConnectError:
        logger.error(f"❌ RAG 검색 연결 실패: Memory 서버({MEMORY_SERVER_BASE_URL})에 접근할 수 없습니다")
        return {"rag_results": []}

    except Exception as e:
        logger.error(f"❌ RAG 검색 실패: {e}")
        return {"rag_results": []}
