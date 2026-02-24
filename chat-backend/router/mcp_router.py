from fastapi import APIRouter, Query

from common.response.code import SuccessCode
from common.response.response_template import ResponseTemplate
from mcp_hub import get_mcp_registry
from service.mcp_service import normalize_mcp_tool

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/tools")
async def list_mcp_tools(
        limit: int = Query(200, ge=1, le=500),
):
    registry = get_mcp_registry()
    tools = await registry.list_all_tools()

    normalized_tools = [normalize_mcp_tool(tool=tool) for tool in tools]
    normalized_tools.sort(
        key=lambda item: (
            -item["recent_score"],
            item["category"],
            item["mcp_name"],
            item["tool_name"],
        )
    )

    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, normalized_tools[:limit])
