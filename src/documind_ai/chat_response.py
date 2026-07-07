from typing import Any

from documind_ai.chat_answer import ChatAnswerRequest, excerpt


class ChatAnswerNormalizationError(ValueError):
    pass


def normalize_chat_answer(raw_text: str, request: ChatAnswerRequest) -> dict[str, Any]:
    content = raw_text.strip()

    if content == "":
        raise ChatAnswerNormalizationError("provider 응답 content는 비어 있지 않아야 합니다.")

    sources = build_sources(request)

    if sources and "[1]" not in content:
        content = f"{content}\n\n[1]"

    return {"content": content, "sources": sources}


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
