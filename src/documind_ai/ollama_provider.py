from json import dumps, loads
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from documind_ai.chat_answer import ChatAnswerRequest, excerpt


class OllamaChatProviderError(RuntimeError):
    pass


class OllamaChatAnswerProvider:
    def __init__(self, base_url: str, model: str, timeout_seconds: int) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/api/chat"
        self.model = model
        self.timeout_seconds = timeout_seconds

    def answer(self, request: ChatAnswerRequest) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": build_ollama_messages(request),
            "stream": False,
        }
        response = self.post_json(payload)
        content = parse_ollama_content(response)

        return {
            "content": ensure_source_marker(content, request),
            "sources": build_sources(request),
        }

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
        except HTTPError as error:
            raise OllamaChatProviderError(f"Ollama 응답 실패: status={error.code}") from error
        except (TimeoutError, URLError) as error:
            reason = getattr(error, "reason", str(error))
            raise OllamaChatProviderError(f"Ollama 연결 실패: {reason}") from error

        try:
            return loads(response_text)
        except ValueError as error:
            raise OllamaChatProviderError("Ollama 응답은 JSON이어야 합니다.") from error


def build_ollama_messages(request: ChatAnswerRequest) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": (
                "당신은 DocuMind의 한국어 문서 분석 assistant입니다. "
                "제공된 문서 근거만 사용해 답변하고, 문서 근거가 있으면 [1] 같은 번호를 표시하세요. "
                "확정 판단이 어려운 항목은 검토 후보로 표현하세요."
            ),
        }
    ]

    for item in request.history:
        role = normalize_history_role(item.role)

        if role is not None:
            messages.append({"role": role, "content": item.content})

    messages.append({"role": "user", "content": build_user_message(request)})

    return messages


def build_user_message(request: ChatAnswerRequest) -> str:
    if not request.contexts:
        return request.question

    context_lines = []

    for index, item in enumerate(request.contexts, start=1):
        context_lines.append(
            f"[{index}] 문서명: {item.title}\n문서 ID: {item.document_id}\n내용:\n{item.content}"
        )

    return f"질문:\n{request.question}\n\n문서 근거:\n\n" + "\n\n".join(context_lines)


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


def ensure_source_marker(content: str, request: ChatAnswerRequest) -> str:
    if not request.contexts or "[1]" in content:
        return content

    return f"{content}\n\n[1]"


def build_sources(request: ChatAnswerRequest) -> list[dict[str, Any]]:
    primary_context = request.contexts[0] if request.contexts else None

    if primary_context is None:
        return []

    return [
        {
            "documentId": primary_context.document_id,
            "title": primary_context.title,
            "quote": excerpt(primary_context.content),
            "relevance": 0.75,
        }
    ]


def normalize_history_role(role: str) -> Optional[str]:
    normalized = role.strip().lower()

    if normalized == "user":
        return "user"

    if normalized == "assistant":
        return "assistant"

    return None
