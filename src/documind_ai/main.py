from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import JSONDecodeError, dumps, loads
from typing import Optional

from documind_ai.chat_answer import (
    ChatAnswerRequestError,
    parse_chat_answer_request,
)
from documind_ai.chat_prompt import build_chat_prompt
from documind_ai.chat_provider import (
    ChatAnswerProvider,
    UnknownChatAnswerProviderError,
    select_chat_answer_provider,
)
from documind_ai.chat_response import (
    ChatAnswerNormalizationError,
    normalize_chat_answer,
)
from documind_ai.config import AppSettings, load_settings
from documind_ai.health import build_health_response
from documind_ai.ollama_provider import (
    OllamaChatProviderError,
    OllamaChatProviderTimeoutError,
)
from documind_ai.openai_provider import (
    OpenAIChatProviderError,
    OpenAIChatProviderTimeoutError,
    OpenAIProviderConfigurationError,
)


def create_handler(
    settings: AppSettings,
    chat_answer_provider: Optional[ChatAnswerProvider] = None,
) -> type[BaseHTTPRequestHandler]:
    provider = chat_answer_provider

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_json(HTTPStatus.NOT_FOUND, {"message": "Not Found"})
                return

            self.send_json(HTTPStatus.OK, build_health_response(settings))

        def do_POST(self) -> None:
            if self.path != "/chat/answers":
                self.send_json(HTTPStatus.NOT_FOUND, {"message": "Not Found"})
                return

            try:
                payload = self.read_json()
                request = parse_chat_answer_request(payload)
                prompt = build_chat_prompt(request)
                raw_answer = self.get_chat_answer_provider().generate(prompt)
                self.send_json(HTTPStatus.OK, normalize_chat_answer(raw_answer, request))
            except (ChatAnswerRequestError, JSONDecodeError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"message": str(error)})
            except (OpenAIProviderConfigurationError, UnknownChatAnswerProviderError) as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": str(error)})
            except (OpenAIChatProviderTimeoutError, OllamaChatProviderTimeoutError) as error:
                self.send_json(HTTPStatus.GATEWAY_TIMEOUT, {"message": str(error)})
            except (OpenAIChatProviderError, OllamaChatProviderError, ChatAnswerNormalizationError) as error:
                self.send_json(HTTPStatus.BAD_GATEWAY, {"message": str(error)})

        def read_json(self) -> object:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ChatAnswerRequestError("Content-Length 헤더가 올바르지 않습니다.") from error

            raw_body = self.rfile.read(content_length)

            if len(raw_body) == 0:
                raise ChatAnswerRequestError("요청 본문은 필수입니다.")

            return loads(raw_body.decode("utf-8"))

        def get_chat_answer_provider(self) -> ChatAnswerProvider:
            nonlocal provider

            if provider is None:
                provider = select_chat_answer_provider(settings)

            return provider

        def send_json(self, status: HTTPStatus, body: object) -> None:
            payload = dumps(body, ensure_ascii=False).encode("utf-8")

            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return HealthHandler


def main() -> None:
    settings = load_settings()
    server = ThreadingHTTPServer((settings.host, settings.port), create_handler(settings))
    print(f"{settings.service_name} listening on {settings.host}:{settings.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
