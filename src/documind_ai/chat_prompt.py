from dataclasses import dataclass

from documind_ai.chat_answer import ChatAnswerRequest


@dataclass(frozen=True)
class BuiltPromptMessage:
    role: str
    content: str


@dataclass(frozen=True)
class BuiltPrompt:
    messages: list[BuiltPromptMessage]


SYSTEM_PROMPT = (
    "당신은 DocuMind의 한국어 업무 문서 분석 assistant입니다. "
    "제공된 문서 근거를 우선 사용하고, 문서에 없는 내용은 추측하지 마세요. "
    "문서 근거가 있으면 [1], [2] 같은 출처 번호를 답변에 포함하세요. "
    "법령, 규정, 리스크는 확정 판단이 아니라 검토 후보로 표현하세요. "
    "실무자가 바로 검토할 수 있도록 간결하게 답변하세요."
)


def build_chat_prompt(request: ChatAnswerRequest) -> BuiltPrompt:
    messages = [BuiltPromptMessage(role="system", content=SYSTEM_PROMPT)]

    for item in request.history:
        messages.append(
            BuiltPromptMessage(
                role=to_prompt_role(item.role),
                content=item.content,
            )
        )

    messages.append(BuiltPromptMessage(role="user", content=build_user_prompt(request)))

    return BuiltPrompt(messages=messages)


def to_prompt_role(role: str) -> str:
    if role == "USER":
        return "user"

    if role == "ASSISTANT":
        return "assistant"

    raise ValueError(f"지원하지 않는 history role입니다: {role}")


def build_user_prompt(request: ChatAnswerRequest) -> str:
    if not request.contexts:
        return f"질문:\n{request.question}"

    context_blocks = []

    for index, item in enumerate(request.contexts, start=1):
        context_blocks.append(
            f"[{index}] 문서명: {item.title}\n"
            f"문서 ID: {item.document_id}\n"
            f"내용:\n{item.content}"
        )

    return f"질문:\n{request.question}\n\n문서 근거:\n\n" + "\n\n".join(context_blocks)
