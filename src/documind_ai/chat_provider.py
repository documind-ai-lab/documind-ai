from typing import Any, Protocol

from documind_ai.chat_answer import ChatAnswerRequest, generate_chat_answer
from documind_ai.config import AppSettings
from documind_ai.ollama_provider import OllamaChatAnswerProvider


class ChatAnswerProvider(Protocol):
    def answer(self, request: ChatAnswerRequest) -> dict[str, Any]:
        ...


class UnknownChatAnswerProviderError(ValueError):
    pass


class StubChatAnswerProvider:
    def answer(self, request: ChatAnswerRequest) -> dict[str, Any]:
        return generate_chat_answer(request)


def select_chat_answer_provider(settings: AppSettings) -> ChatAnswerProvider:
    provider_name = settings.chat_provider.strip().lower()

    if provider_name == "stub":
        return StubChatAnswerProvider()

    if provider_name == "ollama":
        return OllamaChatAnswerProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )

    raise UnknownChatAnswerProviderError(
        f"지원하지 않는 chat provider입니다: {settings.chat_provider}"
    )
