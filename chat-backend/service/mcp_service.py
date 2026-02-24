from typing import Any


def _infer_category(tool_name: str, description: str, mcp_name: str) -> str:
    text = f"{tool_name} {description} {mcp_name}".lower()
    if any(keyword in text for keyword in ["chart", "graph", "plot", "visual"]):
        return "visualization"
    if any(keyword in text for keyword in ["memory", "recall", "note"]):
        return "memory"
    if any(keyword in text for keyword in ["search", "find", "query", "crawl"]):
        return "search"
    if any(keyword in text for keyword in ["slack", "message", "post", "reply"]):
        return "communication"
    return "general"


def _build_schema_preview(input_schema: Any) -> dict[str, Any]:
    if not isinstance(input_schema, dict):
        return {
            "fields": [],
            "required": [],
            "has_schema": False,
        }

    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    if not isinstance(properties, dict):
        properties = {}
    if not isinstance(required, list):
        required = []

    return {
        "fields": list(properties.keys()),
        "required": required,
        "has_schema": bool(properties),
    }


def normalize_mcp_tool(tool: dict[str, Any], recent_score: int = 0) -> dict[str, Any]:
    tool_name = tool.get("name", "")
    description = tool.get("description", "")
    mcp_name = tool.get("source", "unknown")
    input_schema = tool.get("inputSchema", {})

    return {
        "id": f"{mcp_name}:{tool_name}",
        "tool_name": tool_name,
        "mcp_name": mcp_name,
        "description": description,
        "category": _infer_category(tool_name, description, mcp_name),
        "available": True,
        "recent_score": recent_score,
        "input_schema": input_schema,
        "input_schema_preview": _build_schema_preview(input_schema),
    }
