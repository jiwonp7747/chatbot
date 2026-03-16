import unittest
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from common.exception.api_exception import ApiException
from common.exceptionhandler import register_exception_handler
from common.response.code import FailureCode
from db.database import get_db
from router.chat_session_router import router
import service.chat_service as chat_service


class ChatSessionRouterTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        register_exception_handler(self.app)

        async def override_get_db() -> AsyncGenerator[object, None]:
            yield object()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

        self.original_delete_chat_session = chat_service.delete_chat_session
        self.original_update_chat_session_title = chat_service.update_chat_session_title

    def tearDown(self):
        chat_service.delete_chat_session = self.original_delete_chat_session
        chat_service.update_chat_session_title = self.original_update_chat_session_title
        self.app.dependency_overrides.clear()

    def test_delete_session_success(self):
        called = {}

        async def fake_delete_chat_session(thread_id, db):
            called["thread_id"] = thread_id

        chat_service.delete_chat_session = fake_delete_chat_session

        response = self.client.delete("/chat/session/test-thread-id")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status_code"], 200)
        self.assertEqual(called["thread_id"], "test-thread-id")

    def test_update_session_title_success(self):
        async def fake_update_chat_session_title(thread_id, session_title, db):
            return {
                "thread_id": thread_id,
                "session_title": session_title,
                "created_at": "2026-02-13T00:00:00",
                "updated_at": "2026-02-13T00:00:00",
            }

        chat_service.update_chat_session_title = fake_update_chat_session_title

        response = self.client.patch(
            "/chat/session/test-thread-id/title",
            json={"session_title": "새 제목"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status_code"], 200)
        self.assertEqual(body["data"]["thread_id"], "test-thread-id")
        self.assertEqual(body["data"]["session_title"], "새 제목")

    def test_update_session_title_not_found(self):
        async def fake_update_chat_session_title(thread_id, session_title, db):
            raise ApiException(FailureCode.NOT_FOUND_DATA, "존재하지 않는 채팅 세션입니다")

        chat_service.update_chat_session_title = fake_update_chat_session_title

        response = self.client.patch(
            "/chat/session/test-thread-id/title",
            json={"session_title": "없는 세션"},
        )

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["status_code"], 404)
        self.assertEqual(body["message"], "존재하지 않는 채팅 세션입니다")


if __name__ == "__main__":
    unittest.main()
