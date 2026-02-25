import httpx
from fastapi import APIRouter

from common.response.code import SuccessCode
from common.response.response_template import ResponseTemplate

router = APIRouter(prefix="/rag", tags=["rag"])

MEMORY_SERVER_BASE_URL = "http://localhost:6333"


@router.get("/tags/tree")
async def get_rag_tag_tree():
    """Agent Memory 서버에서 계층형 태그 트리를 조회합니다."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{MEMORY_SERVER_BASE_URL}/api/search/tags/tree")
        response.raise_for_status()
        data = response.json()

    tags = data.get("data", {}).get("tags", [])
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, tags)
