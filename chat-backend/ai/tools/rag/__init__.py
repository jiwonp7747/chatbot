from .tag_search import tag_search_tool
from .semantic_search import semantic_search_tool


def get_rag_tools() -> list:
    """RAG 에이전트용 도구 목록 반환"""
    return [tag_search_tool, semantic_search_tool]
