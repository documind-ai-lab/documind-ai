from unittest import TestCase

from documind_ai.chat_prompt import BuiltPrompt, BuiltPromptMessage
from documind_ai.chat_provider import (
    StubChatAnswerProvider,
    UnknownChatAnswerProviderError,
    select_chat_answer_provider,
)
from documind_ai.config import AppSettings
from documind_ai.ollama_provider import OllamaChatAnswerProvider
from documind_ai.openai_provider import (
    OpenAIChatAnswerProvider,
    OpenAIProviderConfigurationError,
)


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
            timeout_seconds=30,
        )

        provider = select_chat_answer_provider(settings)

        self.assertIsInstance(provider, OllamaChatAnswerProvider)

    def test_selects_openai_provider(self):
        settings = AppSettings(
            "documind-ai-test",
            "test",
            "127.0.0.1",
            8001,
            chat_provider="openai",
            openai_api_key="test-key",
            openai_model="gpt-4.1-mini",
        )

        provider = select_chat_answer_provider(settings)

        self.assertIsInstance(provider, OpenAIChatAnswerProvider)

    def test_rejects_openai_provider_without_api_key(self):
        settings = AppSettings(
            "documind-ai-test",
            "test",
            "127.0.0.1",
            8001,
            chat_provider="openai",
            openai_api_key=None,
        )

        with self.assertRaises(OpenAIProviderConfigurationError):
            select_chat_answer_provider(settings)

    def test_stub_provider_generates_raw_text(self):
        prompt = BuiltPrompt(messages=[BuiltPromptMessage(role="user", content="분석해줘")])

        answer = StubChatAnswerProvider().generate(prompt)

        self.assertEqual(answer, "업로드된 문서 기준으로 질문을 검토했습니다.")
