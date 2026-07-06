from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.chat_provider import (
    StubChatAnswerProvider,
    UnknownChatAnswerProviderError,
    select_chat_answer_provider,
)
from documind_ai.config import AppSettings
from documind_ai.ollama_provider import OllamaChatAnswerProvider


class ChatProviderTest(TestCase):
    def test_selects_stub_provider_by_default(self):
        settings = AppSettings("documind-ai-test", "test", "127.0.0.1", 8001)

        provider = select_chat_answer_provider(settings)

        self.assertIsInstance(provider, StubChatAnswerProvider)

    def test_rejects_unknown_provider(self):
        settings = AppSettings(
            "documind-ai-test",
            "test",
            "127.0.0.1",
            8001,
            chat_provider="unknown",
        )

        with self.assertRaises(UnknownChatAnswerProviderError):
            select_chat_answer_provider(settings)

    def test_selects_ollama_provider(self):
        settings = AppSettings(
            "documind-ai-test",
            "test",
            "127.0.0.1",
            8001,
            chat_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_model="llama3.2",
            ollama_timeout_seconds=30,
        )

        provider = select_chat_answer_provider(settings)

        self.assertIsInstance(provider, OllamaChatAnswerProvider)

    def test_stub_provider_keeps_chat_answer_contract(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "견적서 리스크를 알려줘",
                "contexts": [
                    {
                        "documentId": "document-1",
                        "title": "견적서.txt",
                        "content": "총액은 1000만원입니다.",
                    }
                ],
                "history": [],
            }
        )

        answer = StubChatAnswerProvider().answer(request)

        self.assertIn("[1]", answer["content"])
        self.assertEqual(answer["sources"][0]["documentId"], "document-1")
