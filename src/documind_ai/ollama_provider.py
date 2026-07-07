from json import dumps, loads
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from documind_ai.chat_prompt import BuiltPrompt


class OllamaChatProviderError(RuntimeError):
    pass


class OllamaChatProviderTimeoutError(OllamaChatProviderError):
    pass


class OllamaChatAnswerProvider:
    def __init__(self, base_url: str, model: str, timeout_seconds: int) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/api/chat"
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: BuiltPrompt) -> str:
        payload = {
            "model": self.model,
            "messages": build_ollama_messages(prompt),
            "stream": False,
        }
        response = self.post_json(payload)
        return parse_ollama_content(response)

    def post_json(self, payload: dict[str, Any]) -> object:
        http_request = Request(
            self.endpoint,
            data=dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
        except TimeoutError as error:
            raise OllamaChatProviderTimeoutError("Ollama 요청 시간이 초과되었습니다.") from error
        except HTTPError as error:
            raise OllamaChatProviderError(f"Ollama 응답 실패: status={error.code}") from error
        except URLError as error:
            reason = getattr(error, "reason", str(error))
            raise OllamaChatProviderError(f"Ollama 연결 실패: {reason}") from error

        try:
            return loads(response_text)
        except ValueError as error:
            raise OllamaChatProviderError("Ollama 응답은 JSON이어야 합니다.") from error


def build_ollama_messages(prompt: BuiltPrompt) -> list[dict[str, str]]:
    return [{"role": item.role, "content": item.content} for item in prompt.messages]


def parse_ollama_content(response: object) -> str:
    if not isinstance(response, dict):
        raise OllamaChatProviderError("Ollama 응답은 JSON object여야 합니다.")

    message = response.get("message")

    if not isinstance(message, dict):
        raise OllamaChatProviderError("Ollama 응답 message는 JSON object여야 합니다.")

    content = message.get("content")

    if not isinstance(content, str) or content.strip() == "":
        raise OllamaChatProviderError("Ollama 응답 message.content는 비어 있지 않은 문자열이어야 합니다.")

    return content
