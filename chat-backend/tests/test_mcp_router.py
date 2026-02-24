import unittest
import importlib
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

mcp_router_module = importlib.import_module("router.mcp_router")
router = mcp_router_module.router


class FakeRegistry:
    async def list_all_tools(self):
        return [
            {
                "name": "search_docs",
                "description": "Search docs in remote index",
                "source": "agent-memory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "draw_chart",
                "description": "Render chart with EChart",
                "source": "echart",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {"type": "object"},
                    },
                    "required": ["spec"],
                },
            },
        ]


class McpRouterTests(unittest.TestCase):
    def setUp(self):
        self.get_registry_patcher = patch("router.mcp_router.get_mcp_registry", return_value=FakeRegistry())
        self.get_registry_patcher.start()

        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.get_registry_patcher.stop()

    def test_list_mcp_tools_returns_normalized_items(self):
        response = self.client.get("/mcp/tools")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status_code"], 200)
        self.assertEqual(len(body["data"]), 2)

        first = body["data"][0]
        self.assertIn("tool_name", first)
        self.assertIn("mcp_name", first)
        self.assertIn("category", first)
        self.assertIn("input_schema", first)
        self.assertIn("input_schema_preview", first)

    def test_list_mcp_tools_supports_limit(self):
        response = self.client.get("/mcp/tools?limit=1")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["data"]), 1)


if __name__ == "__main__":
    unittest.main()
