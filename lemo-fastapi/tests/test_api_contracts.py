from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main
from helpers.runtime_cache import clear_local_cache


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        asyncio.run(clear_local_cache())
        self.client = TestClient(main.app)

    def test_query_rejects_non_bearer_auth_header(self) -> None:
        response = self.client.post(
            "/query?session_id=s1",
            headers={"Authorization": "not-a-bearer-token"},
            json={"user_query": "hello"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "User authentication required")

    def test_query_rejects_invalid_bearer_token(self) -> None:
        response = self.client.post(
            "/query?session_id=s1",
            headers={"Authorization": "Bearer invalid-token"},
            json={"user_query": "hello"},
        )
        self.assertEqual(response.status_code, 401)

    def test_nonce_invalid_wallet_returns_400(self) -> None:
        response = self.client.get("/auth/nonce/notanaddress")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid wallet address provided")

    def test_login_invalid_siwe_message_returns_400(self) -> None:
        response = self.client.post(
            "/auth/login/0x1234567890123456789012345678901234567890",
            json={"message": "not-a-siwe-message", "signature": "0xdead"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid SIWE message")

    def test_query_uses_answer_cache_for_identical_request(self) -> None:
        fake_user = SimpleNamespace(id="user-1")
        fake_session = {
            "id": "s1",
            "current_url": "https://www.amazon.in/dp/B09XS7JWHH",
            "current_domain": "amazon.in",
            "chat_messages": [],
        }
        pipeline = AsyncMock(
            return_value={
                "final_answer": "Cached answer",
                "intent": "ask",
                "scope": "current_page",
                "next_action": "scrape_current_page",
                "scraped_data": [],
            }
        )

        with (
            patch("controllers.query_handler.get_optional_user", AsyncMock(return_value=fake_user)),
            patch("controllers.query_handler.get_session_details", AsyncMock(return_value=fake_session)),
            patch("controllers.query_handler.run_lemo_pipeline", pipeline),
            patch("controllers.query_handler.add_chats", AsyncMock(return_value={"status": "success"})),
        ):
            headers = {"Authorization": "Bearer mocked-valid-token"}
            body = {"user_query": "tell me about this"}

            first = self.client.post("/query?session_id=s1", headers=headers, json=body)
            second = self.client.post("/query?session_id=s1", headers=headers, json=body)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["answer"], "Cached answer")
        self.assertEqual(second.json()["answer"], "Cached answer")
        self.assertEqual(pipeline.await_count, 1)


if __name__ == "__main__":
    unittest.main()
