from json import dumps, loads
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from documind_ai.chat_prompt import BuiltPrompt


class OpenAIProviderConfigurationError(ValueError):
    pass


class OpenAIChatProviderError(RuntimeError):
    pass


class OpenAIChatProviderTimeoutError(OpenAIChatProviderError):
    pass


class OpenAIChatAnswerProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: int) -> None:
        if api_key.strip() == "":
            raise OpenAIProviderConfigurationError("OpenAI API key가 설정되지 않았습니다.")

        self.endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: BuiltPrompt) -> str:
        payload = {
            "model": self.model,
            "messages": build_openai_messages(prompt),
        }
        response = self.post_json(payload)
        return parse_openai_content(response)

    def post_json(self, payload: dict[str, Any]) -> object:
        http_request = Request(
            self.endpoint,
            data=dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
        except TimeoutError as error:
            raise OpenAIChatProviderTimeoutError("OpenAI 요청 시간이 초과되었습니다.") from error
        except HTTPError as error:
            raise OpenAIChatProviderError(f"OpenAI 응답 실패: status={error.code}") from error
        except URLError as error:
            reason = getattr(error, "reason", str(error))
            raise OpenAIChatProviderError(f"OpenAI 연결 실패: {reason}") from error

        try:
            return loads(response_text)
        except ValueError as error:
            raise OpenAIChatProviderError("OpenAI 응답은 JSON이어야 합니다.") from error


def build_openai_messages(prompt: BuiltPrompt) -> list[dict[str, str]]:
    return [{"role": item.role, "content": item.content} for item in prompt.messages]


def parse_openai_content(response: object) -> str:
    if not isinstance(response, dict):
        raise OpenAIChatProviderError("OpenAI 응답은 JSON object여야 합니다.")

    choices = response.get("choices")

    if not isinstance(choices, list) or len(choices) == 0:
        raise OpenAIChatProviderError("OpenAI 응답 choices는 비어 있지 않은 배열이어야 합니다.")

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        raise OpenAIChatProviderError("OpenAI 응답 choices[0]는 JSON object여야 합니다.")

    message = first_choice.get("message")

    if not isinstance(message, dict):
        raise OpenAIChatProviderError("OpenAI 응답 message는 JSON object여야 합니다.")

    content = message.get("content")

    if not isinstance(content, str) or content.strip() == "":
        raise OpenAIChatProviderError("OpenAI 응답 message.content는 비어 있지 않은 문자열이어야 합니다.")

    return content
