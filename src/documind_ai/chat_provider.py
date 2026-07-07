from typing import Protocol

from documind_ai.chat_prompt import BuiltPrompt
from documind_ai.config import AppSettings
from documind_ai.ollama_provider import OllamaChatAnswerProvider
from documind_ai.openai_provider import (
    OpenAIChatAnswerProvider,
    OpenAIProviderConfigurationError,
)


class ChatAnswerProvider(Protocol):
    def generate(self, prompt: BuiltPrompt) -> str:
        ...


class UnknownChatAnswerProviderError(ValueError):
    pass


class StubChatAnswerProvider:
    def generate(self, prompt: BuiltPrompt) -> str:
        return "업로드된 문서 기준으로 질문을 검토했습니다."


def select_chat_answer_provider(settings: AppSettings) -> ChatAnswerProvider:
    provider_name = settings.chat_provider.strip().lower()

    if provider_name == "stub":
        return StubChatAnswerProvider()

    if provider_name == "ollama":
        return OllamaChatAnswerProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.timeout_seconds,
        )

    if provider_name == "openai":
        if settings.openai_api_key is None:
            raise OpenAIProviderConfigurationError("OpenAI API key가 설정되지 않았습니다.")

        return OpenAIChatAnswerProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout_seconds=settings.timeout_seconds,
        )

    raise UnknownChatAnswerProviderError(
        f"지원하지 않는 chat provider입니다: {settings.chat_provider}"
    )
