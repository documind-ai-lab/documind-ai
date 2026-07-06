from dataclasses import dataclass
from typing import Any


class ChatAnswerRequestError(ValueError):
    pass


@dataclass(frozen=True)
class ChatContextItem:
    document_id: str
    title: str
    content: str


@dataclass(frozen=True)
class ChatHistoryItem:
    role: str
    content: str


@dataclass(frozen=True)
class ChatAnswerRequest:
    project_id: str
    owner_id: str
    question: str
    contexts: list[ChatContextItem]
    history: list[ChatHistoryItem]


ALLOWED_HISTORY_ROLES = {"USER", "ASSISTANT"}


def parse_chat_answer_request(payload: object) -> ChatAnswerRequest:
    if not isinstance(payload, dict):
        raise ChatAnswerRequestError("요청 본문은 JSON object여야 합니다.")

    project_id = require_string(payload, "projectId")
    owner_id = require_string(payload, "ownerId")
    question = require_string(payload, "question")
    contexts = parse_contexts(payload.get("contexts"))
    history = parse_history(payload.get("history"))

    return ChatAnswerRequest(project_id, owner_id, question, contexts, history)


def generate_chat_answer(request: ChatAnswerRequest) -> dict[str, Any]:
    primary_context = request.contexts[0] if request.contexts else None

    if primary_context is None:
        return {
            "content": "분석 가능한 문서 텍스트가 아직 없습니다. 문서 업로드와 텍스트 추출이 완료되면 문서 근거를 포함해 답변할 수 있습니다.",
            "sources": [],
        }

    quote = excerpt(primary_context.content)

    return {
        "content": f"업로드된 문서 기준으로 질문을 검토했습니다. [1]\n\n질문: {request.question}\n\n핵심 근거: {quote}",
        "sources": [
            {
                "documentId": primary_context.document_id,
                "title": primary_context.title,
                "quote": quote,
                "relevance": 0.85,
            }
        ],
    }


def parse_contexts(value: object) -> list[ChatContextItem]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ChatAnswerRequestError("contexts는 배열이어야 합니다.")

    contexts: list[ChatContextItem] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ChatAnswerRequestError(f"contexts[{index}]는 JSON object여야 합니다.")

        contexts.append(
            ChatContextItem(
                document_id=require_string(item, "documentId"),
                title=require_string(item, "title"),
                content=require_string(item, "content"),
            )
        )

    return contexts


def parse_history(value: object) -> list[ChatHistoryItem]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ChatAnswerRequestError("history는 배열이어야 합니다.")

    history: list[ChatHistoryItem] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ChatAnswerRequestError(f"history[{index}]는 JSON object여야 합니다.")

        history.append(
            ChatHistoryItem(
                role=parse_history_role(item, index),
                content=require_string(item, "content"),
            )
        )

    return history


def parse_history_role(item: dict[str, object], index: int) -> str:
    role = require_string(item, "role").strip().upper()

    if role not in ALLOWED_HISTORY_ROLES:
        raise ChatAnswerRequestError(f"history[{index}].role은 USER 또는 ASSISTANT여야 합니다.")

    return role


def require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)

    if not isinstance(value, str) or value.strip() == "":
        raise ChatAnswerRequestError(f"{key}는 비어 있지 않은 문자열이어야 합니다.")

    return value


def excerpt(content: str) -> str:
    normalized = " ".join(content.split())

    if normalized == "":
        return "문서 텍스트가 비어 있습니다."

    return f"{normalized[:300]}..." if len(normalized) > 300 else normalized
