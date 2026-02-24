import httpx
from fastapi import APIRouter

from common.response.code import SuccessCode
from common.response.response_template import ResponseTemplate

router = APIRouter(prefix="/rag", tags=["rag"])

MEMORY_SERVER_BASE_URL = "http://localhost:6333"


@router.get("/tags")
async def list_rag_tags():
    """Agent Memory 서버에서 사용 가능한 태그 목록을 조회합니다."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{MEMORY_SERVER_BASE_URL}/api/manage/tags/stats")
        response.raise_for_status()
        data = response.json()

    # Extract just tag names from the response
    tags_data = data.get("data", {}).get("tags", [])
    tag_names = [item["tag"] for item in tags_data if item.get("tag")]

    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, tag_names)
