# AI Provider Prompt Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provider-agnostic prompt contract so `documind-ai` can use `stub`, local `ollama`, and `openai` providers without changing the existing `/chat/answers` HTTP response shape.

**Architecture:** Keep `/chat/answers` input and output contracts stable. Move prompt construction into `build_chat_prompt`, make providers return raw answer text through `generate(prompt)`, and centralize `{ content, sources }` creation in `normalize_chat_answer`.

**Tech Stack:** Python 3.11+, standard library only, `unittest`, `http.server`, `urllib.request`, current `src/documind_ai` package layout.

## Global Constraints

- Do not add third-party runtime dependencies.
- Keep `/chat/answers` response shape as `{ content, sources }`.
- Keep backend and client contracts unchanged.
- Do not implement embedding, vector search, chunking, reranking, streaming, or automatic provider fallback.
- Do not call real Ollama or OpenAI services from default automated tests.
- Do not log API keys, Authorization headers, full document text, or raw provider responses.
- Use `docs/specs/` for project planning documents.
- Commit messages must use Korean conventional titles and body sections: `배경`, `판단`, `검증`, `남은 리스크`.

---

## File Structure

- Create `src/documind_ai/chat_prompt.py`
  - Owns `BuiltPromptMessage`, `BuiltPrompt`, and `build_chat_prompt`.
  - Converts `ChatAnswerRequest` into provider-neutral chat messages.

- Create `src/documind_ai/chat_response.py`
  - Owns `ChatAnswerNormalizationError` and `normalize_chat_answer`.
  - Converts raw provider text plus request contexts into `{ content, sources }`.

- Modify `src/documind_ai/chat_provider.py`
  - Changes provider protocol from `answer(request)` to `generate(prompt)`.
  - Keeps provider selection in one place.
  - Moves stub provider to raw text generation.

- Modify `src/documind_ai/ollama_provider.py`
  - Consumes `BuiltPrompt`.
  - Removes request parsing, source building, and source marker normalization from provider.
  - Keeps only Ollama payload creation, HTTP call, and content parsing.

- Create `src/documind_ai/openai_provider.py`
  - Consumes `BuiltPrompt`.
  - Calls OpenAI-compatible HTTP endpoint using standard library.
  - Returns raw answer text.

- Modify `src/documind_ai/config.py`
  - Adds OpenAI API key/model settings.
  - Adds common timeout setting.
  - Preserves old Ollama timeout env fallback for local compatibility.

- Modify `src/documind_ai/main.py`
  - Builds prompt, calls provider, normalizes response.
  - Maps validation, configuration, provider, timeout, and normalization errors to HTTP status codes.

- Modify `README.md` and `.env.example`
  - Documents `stub`, `ollama`, and `openai` provider settings.
  - Documents that OpenAI smoke tests are manual because they cost money.

- Add tests:
  - `tests/test_chat_prompt.py`
  - `tests/test_chat_response.py`
  - `tests/test_openai_provider.py`

- Modify tests:
  - `tests/test_chat_provider.py`
  - `tests/test_ollama_provider.py`
  - `tests/test_http_server.py`
  - `tests/test_chat_answer.py`

---

### Task 1: Prompt Builder

**Files:**
- Create: `src/documind_ai/chat_prompt.py`
- Create: `tests/test_chat_prompt.py`

**Interfaces:**
- Consumes: `ChatAnswerRequest`, `ChatContextItem`, `ChatHistoryItem` from `documind_ai.chat_answer`
- Produces:
  - `BuiltPromptMessage(role: str, content: str)`
  - `BuiltPrompt(messages: list[BuiltPromptMessage])`
  - `build_chat_prompt(request: ChatAnswerRequest) -> BuiltPrompt`

- [ ] **Step 1: Write the failing prompt builder tests**

Create `tests/test_chat_prompt.py`:

```python
from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.chat_prompt import build_chat_prompt


class ChatPromptTest(TestCase):
    def test_builds_prompt_without_contexts(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "분석해줘",
                "contexts": [],
                "history": [],
            }
        )

        prompt = build_chat_prompt(request)

        self.assertEqual(prompt.messages[0].role, "system")
        self.assertIn("한국어 업무 문서 분석", prompt.messages[0].content)
        self.assertIn("추측하지", prompt.messages[0].content)
        self.assertEqual(prompt.messages[-1].role, "user")
        self.assertEqual(prompt.messages[-1].content, "질문:\n분석해줘")

    def test_builds_prompt_with_contexts_and_source_numbers(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "견적서 리스크를 알려줘",
                "contexts": [
                    {
                        "documentId": "document-1",
                        "title": "견적서.txt",
                        "content": "총액은 1000만원입니다.",
                    },
                    {
                        "documentId": "document-2",
                        "title": "제안서.txt",
                        "content": "납기는 별도 협의입니다.",
                    },
                ],
                "history": [],
            }
        )

        prompt = build_chat_prompt(request)
        user_message = prompt.messages[-1].content

        self.assertIn("[1] 문서명: 견적서.txt", user_message)
        self.assertIn("문서 ID: document-1", user_message)
        self.assertIn("[2] 문서명: 제안서.txt", user_message)
        self.assertIn("문서 ID: document-2", user_message)
        self.assertIn("질문:\n견적서 리스크를 알려줘", user_message)

    def test_preserves_history_order(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "다시 설명해줘",
                "contexts": [],
                "history": [
                    {"role": "USER", "content": "먼저 요약해줘"},
                    {"role": "ASSISTANT", "content": "요약했습니다. [1]"},
                ],
            }
        )

        prompt = build_chat_prompt(request)

        self.assertEqual(prompt.messages[1].role, "user")
        self.assertEqual(prompt.messages[1].content, "먼저 요약해줘")
        self.assertEqual(prompt.messages[2].role, "assistant")
        self.assertEqual(prompt.messages[2].content, "요약했습니다. [1]")
        self.assertEqual(prompt.messages[3].role, "user")
        self.assertEqual(prompt.messages[3].content, "질문:\n다시 설명해줘")

    def test_system_prompt_contains_risk_and_source_policy(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "리스크 알려줘",
                "contexts": [],
                "history": [],
            }
        )

        system_message = build_chat_prompt(request).messages[0].content

        self.assertIn("[1]", system_message)
        self.assertIn("검토 후보", system_message)
        self.assertIn("문서 근거", system_message)
```

- [ ] **Step 2: Run the prompt builder tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_chat_prompt
```

Expected: FAIL with `ModuleNotFoundError: No module named 'documind_ai.chat_prompt'`.

- [ ] **Step 3: Implement `chat_prompt.py`**

Create `src/documind_ai/chat_prompt.py`:

```python
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
```

- [ ] **Step 4: Run prompt builder tests and verify pass**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_chat_prompt
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/documind_ai/chat_prompt.py tests/test_chat_prompt.py
git commit -m "feat: AI 채팅 prompt builder 추가" -m "배경
provider별 prompt 조립을 분산시키지 않기 위해 공통 prompt builder가 필요합니다.

판단
ChatAnswerRequest를 provider 공통 BuiltPrompt로 변환하는 chat_prompt 모듈을 추가했습니다.

검증
PYTHONPATH=src python3 -m unittest tests.test_chat_prompt 통과

남은 리스크
provider 연결은 후속 task에서 반영합니다."
```

---

### Task 2: Response Normalizer

**Files:**
- Create: `src/documind_ai/chat_response.py`
- Create: `tests/test_chat_response.py`
- Modify: `tests/test_chat_answer.py`

**Interfaces:**
- Consumes: `ChatAnswerRequest`, `excerpt`
- Produces:
  - `ChatAnswerNormalizationError(ValueError)`
  - `normalize_chat_answer(raw_text: str, request: ChatAnswerRequest) -> dict[str, object]`

- [ ] **Step 1: Write the failing normalizer tests**

Create `tests/test_chat_response.py`:

```python
from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.chat_response import (
    ChatAnswerNormalizationError,
    normalize_chat_answer,
)


class ChatResponseTest(TestCase):
    def test_returns_empty_sources_without_contexts(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "분석해줘",
                "contexts": [],
                "history": [],
            }
        )

        answer = normalize_chat_answer("문서가 아직 없습니다.", request)

        self.assertEqual(answer, {"content": "문서가 아직 없습니다.", "sources": []})

    def test_builds_source_from_first_context(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "견적서 리스크를 알려줘",
                "contexts": [
                    {
                        "documentId": "document-1",
                        "title": "견적서.txt",
                        "content": "총액은 1000만원이며 납기는 별도 협의입니다.",
                    }
                ],
                "history": [],
            }
        )

        answer = normalize_chat_answer("견적서 기준 검토 결과입니다. [1]", request)

        self.assertEqual(answer["content"], "견적서 기준 검토 결과입니다. [1]")
        self.assertEqual(
            answer["sources"],
            [
                {
                    "documentId": "document-1",
                    "title": "견적서.txt",
                    "quote": "총액은 1000만원이며 납기는 별도 협의입니다.",
                    "relevance": 0.75,
                }
            ],
        )

    def test_adds_source_marker_when_context_exists(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "견적서 리스크를 알려줘",
                "contexts": [
                    {
                        "documentId": "document-1",
                        "title": "견적서.txt",
                        "content": "총액은 1000만원입니다.",
                    }
                ],
                "history": [],
            }
        )

        answer = normalize_chat_answer("견적서 기준 검토 결과입니다.", request)

        self.assertEqual(answer["content"], "견적서 기준 검토 결과입니다.\n\n[1]")

    def test_rejects_empty_raw_text(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "분석해줘",
                "contexts": [],
                "history": [],
            }
        )

        with self.assertRaises(ChatAnswerNormalizationError):
            normalize_chat_answer("   ", request)
```

- [ ] **Step 2: Run the normalizer tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_chat_response
```

Expected: FAIL with `ModuleNotFoundError: No module named 'documind_ai.chat_response'`.

- [ ] **Step 3: Implement `chat_response.py`**

Create `src/documind_ai/chat_response.py`:

```python
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
```

- [ ] **Step 4: Run normalizer tests and verify pass**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_chat_response
```

Expected: PASS.

- [ ] **Step 5: Keep existing chat answer tests passing**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_chat_answer
```

Expected: PASS. Existing `generate_chat_answer` remains available until Task 3 replaces provider flow.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/documind_ai/chat_response.py tests/test_chat_response.py
git commit -m "feat: AI 채팅 응답 정규화 추가" -m "배경
provider raw text와 /chat/answers 응답 shape를 분리하기 위해 공통 정규화 함수가 필요합니다.

판단
provider 응답 text를 content와 request context 기반 sources로 변환하는 chat_response 모듈을 추가했습니다.

검증
PYTHONPATH=src python3 -m unittest tests.test_chat_response 통과
PYTHONPATH=src python3 -m unittest tests.test_chat_answer 통과

남은 리스크
provider protocol 전환은 후속 task에서 반영합니다."
```

---

### Task 3: Provider Protocol Refactor

**Files:**
- Modify: `src/documind_ai/chat_provider.py`
- Modify: `src/documind_ai/main.py`
- Modify: `tests/test_chat_provider.py`
- Modify: `tests/test_http_server.py`

**Interfaces:**
- Consumes: `BuiltPrompt`, `build_chat_prompt`, `normalize_chat_answer`
- Produces:
  - `ChatAnswerProvider.generate(prompt: BuiltPrompt) -> str`
  - HTTP `/chat/answers` still returns `{ content, sources }`

- [ ] **Step 1: Update provider tests to the new protocol**

In `tests/test_chat_provider.py`, change imports and the stub contract test:

```python
from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.chat_prompt import build_chat_prompt
from documind_ai.chat_provider import (
    StubChatAnswerProvider,
    UnknownChatAnswerProviderError,
    select_chat_answer_provider,
)
from documind_ai.config import AppSettings
from documind_ai.ollama_provider import OllamaChatAnswerProvider


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

    def test_stub_provider_generates_raw_answer_text(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "견적서 리스크를 알려줘",
                "contexts": [
                    {
                        "documentId": "document-1",
                        "title": "견적서.txt",
                        "content": "총액은 1000만원입니다.",
                    }
                ],
                "history": [],
            }
        )

        content = StubChatAnswerProvider().generate(build_chat_prompt(request))

        self.assertIn("업로드된 문서 기준", content)
```

- [ ] **Step 2: Update HTTP server fake provider tests**

In `tests/test_http_server.py`, change fake providers:

```python
class FakeChatAnswerProvider:
    def generate(self, prompt):
        return f"provider answer: {prompt.messages[-1].content}"


class FailingChatAnswerProvider:
    def generate(self, prompt):
        raise OllamaChatProviderError("Ollama 연결 실패: refused")
```

Then update assertion in `test_chat_answer_endpoint_uses_injected_provider`:

```python
self.assertEqual(body["content"], "provider answer: 질문:\n분석해줘")
self.assertEqual(body["sources"], [])
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_chat_provider tests.test_http_server
```

Expected: FAIL because providers still implement `answer(request)`.

- [ ] **Step 4: Refactor `chat_provider.py`**

Replace `src/documind_ai/chat_provider.py` with:

```python
from typing import Protocol

from documind_ai.chat_prompt import BuiltPrompt
from documind_ai.config import AppSettings
from documind_ai.ollama_provider import OllamaChatAnswerProvider


class ChatAnswerProvider(Protocol):
    def generate(self, prompt: BuiltPrompt) -> str:
        ...


class UnknownChatAnswerProviderError(ValueError):
    pass


class StubChatAnswerProvider:
    def generate(self, prompt: BuiltPrompt) -> str:
        user_message = prompt.messages[-1].content
        return f"업로드된 문서 기준으로 질문을 검토했습니다. [1]\n\n{user_message}"


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

    raise UnknownChatAnswerProviderError(
        f"지원하지 않는 chat provider입니다: {settings.chat_provider}"
    )
```

- [ ] **Step 5: Refactor `main.py` endpoint flow**

In `src/documind_ai/main.py`, add imports:

```python
from documind_ai.chat_prompt import build_chat_prompt
from documind_ai.chat_response import (
    ChatAnswerNormalizationError,
    normalize_chat_answer,
)
```

Replace the provider call inside `do_POST`:

```python
request = parse_chat_answer_request(payload)
prompt = build_chat_prompt(request)
content = provider.generate(prompt)
self.send_json(HTTPStatus.OK, normalize_chat_answer(content, request))
```

Add normalization error mapping:

```python
except ChatAnswerNormalizationError as error:
    self.send_json(HTTPStatus.BAD_GATEWAY, {"message": str(error)})
```

- [ ] **Step 6: Run provider and HTTP tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_chat_provider tests.test_http_server
```

Expected: PASS.

- [ ] **Step 7: Run full current test suite**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Expected: FAIL only in `tests.test_ollama_provider` because Ollama provider still uses old request-based methods. Fix happens in Task 4.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add src/documind_ai/chat_provider.py src/documind_ai/main.py tests/test_chat_provider.py tests/test_http_server.py
git commit -m "feat: AI provider protocol을 prompt 기반으로 전환" -m "배경
provider가 request를 직접 해석하면 prompt 정책과 모델 호출 책임이 섞입니다.

판단
provider protocol을 generate(BuiltPrompt) 형태로 전환하고 HTTP endpoint에서 prompt 생성과 응답 정규화를 담당하도록 변경했습니다.

검증
PYTHONPATH=src python3 -m unittest tests.test_chat_provider tests.test_http_server 통과

남은 리스크
Ollama provider의 기존 request 기반 구현은 다음 task에서 전환합니다."
```

---

### Task 4: Ollama Provider Refactor

**Files:**
- Modify: `src/documind_ai/ollama_provider.py`
- Modify: `tests/test_ollama_provider.py`

**Interfaces:**
- Consumes: `BuiltPrompt`
- Produces:
  - `OllamaChatAnswerProvider.generate(prompt: BuiltPrompt) -> str`
  - `build_ollama_messages(prompt: BuiltPrompt) -> list[dict[str, str]]`

- [ ] **Step 1: Update Ollama provider tests**

Replace request-based tests in `tests/test_ollama_provider.py` with prompt-based tests:

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps, loads
from threading import Thread
from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.chat_prompt import build_chat_prompt
from documind_ai.ollama_provider import (
    OllamaChatAnswerProvider,
    OllamaChatProviderError,
    build_ollama_messages,
)


class OllamaProviderTest(TestCase):
    def test_builds_ollama_messages_from_built_prompt(self):
        prompt = build_chat_prompt(
            parse_chat_answer_request(
                {
                    "projectId": "project-1",
                    "ownerId": "owner-1",
                    "question": "견적서 리스크를 알려줘",
                    "contexts": [
                        {
                            "documentId": "document-1",
                            "title": "견적서.txt",
                            "content": "총액은 1000만원입니다.",
                        }
                    ],
                    "history": [{"role": "USER", "content": "이전 질문"}],
                }
            )
        )

        messages = build_ollama_messages(prompt)

        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1], {"role": "user", "content": "이전 질문"})
        self.assertEqual(messages[2]["role"], "user")
        self.assertIn("질문:", messages[2]["content"])
        self.assertIn("[1] 문서명: 견적서.txt", messages[2]["content"])

    def test_calls_ollama_chat_api_and_returns_raw_text(self):
        ollama = OllamaStubServer(
            {
                "message": {
                    "role": "assistant",
                    "content": "견적서 기준 검토 결과입니다. [1]",
                },
                "done": True,
            }
        )
        ollama.start()

        try:
            provider = OllamaChatAnswerProvider(
                base_url=ollama.base_url,
                model="llama3.2",
                timeout_seconds=5,
            )
            prompt = build_chat_prompt(
                parse_chat_answer_request(
                    {
                        "projectId": "project-1",
                        "ownerId": "owner-1",
                        "question": "견적서 리스크를 알려줘",
                        "contexts": [],
                        "history": [],
                    }
                )
            )

            content = provider.generate(prompt)

            self.assertEqual(ollama.requests[0]["path"], "/api/chat")
            self.assertEqual(ollama.requests[0]["body"]["model"], "llama3.2")
            self.assertEqual(ollama.requests[0]["body"]["stream"], False)
            self.assertEqual(content, "견적서 기준 검토 결과입니다. [1]")
        finally:
            ollama.stop()
```

Keep the existing invalid shape and invalid JSON tests, but call `provider.generate(prompt)` instead of `provider.answer(request)`.

- [ ] **Step 2: Run Ollama tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_ollama_provider
```

Expected: FAIL because `OllamaChatAnswerProvider.generate` is missing.

- [ ] **Step 3: Refactor `ollama_provider.py`**

Replace request-specific functions with prompt-specific functions:

```python
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
```

- [ ] **Step 4: Run Ollama tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_ollama_provider
```

Expected: PASS.

- [ ] **Step 5: Run full suite**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add src/documind_ai/ollama_provider.py tests/test_ollama_provider.py
git commit -m "feat: Ollama provider를 prompt 기반으로 전환" -m "배경
Ollama provider가 request parsing과 source 생성을 함께 담당하면 provider 책임이 커집니다.

판단
Ollama provider를 BuiltPrompt 입력과 raw text 출력 구조로 전환하고 응답 정규화 책임을 제거했습니다.

검증
PYTHONPATH=src python3 -m unittest tests.test_ollama_provider 통과
PYTHONPATH=src python3 -m unittest discover -s tests 통과

남은 리스크
OpenAI provider는 다음 task에서 추가합니다."
```

---

### Task 5: OpenAI Provider and Configuration

**Files:**
- Create: `src/documind_ai/openai_provider.py`
- Create: `tests/test_openai_provider.py`
- Modify: `src/documind_ai/config.py`
- Modify: `src/documind_ai/chat_provider.py`
- Modify: `tests/test_chat_provider.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `BuiltPrompt`, `AppSettings`
- Produces:
  - `OpenAIChatAnswerProvider.generate(prompt: BuiltPrompt) -> str`
  - `OpenAIProviderConfigurationError(ValueError)`
  - `OpenAIChatProviderError(RuntimeError)`
  - `OpenAIChatProviderTimeoutError(OpenAIChatProviderError)`
  - `AppSettings.openai_api_key: str | None`
  - `AppSettings.openai_model: str`
  - `AppSettings.timeout_seconds: int`

- [ ] **Step 1: Write OpenAI provider tests**

Create `tests/test_openai_provider.py`:

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps, loads
from threading import Thread
from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.chat_prompt import build_chat_prompt
from documind_ai.openai_provider import (
    OpenAIChatAnswerProvider,
    OpenAIChatProviderError,
)


class OpenAIProviderTest(TestCase):
    def test_calls_openai_chat_completions_and_returns_raw_text(self):
        openai = OpenAIStubServer(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "견적서 기준 검토 결과입니다. [1]",
                        }
                    }
                ]
            }
        )
        openai.start()

        try:
            provider = OpenAIChatAnswerProvider(
                base_url=openai.base_url,
                api_key="test-key",
                model="gpt-4.1-mini",
                timeout_seconds=5,
            )
            prompt = build_chat_prompt(
                parse_chat_answer_request(
                    {
                        "projectId": "project-1",
                        "ownerId": "owner-1",
                        "question": "견적서 리스크를 알려줘",
                        "contexts": [],
                        "history": [],
                    }
                )
            )

            content = provider.generate(prompt)

            self.assertEqual(openai.requests[0]["path"], "/v1/chat/completions")
            self.assertEqual(openai.requests[0]["headers"]["Authorization"], "Bearer test-key")
            self.assertEqual(openai.requests[0]["body"]["model"], "gpt-4.1-mini")
            self.assertEqual(openai.requests[0]["body"]["messages"][0]["role"], "system")
            self.assertEqual(content, "견적서 기준 검토 결과입니다. [1]")
        finally:
            openai.stop()

    def test_rejects_empty_openai_content(self):
        openai = OpenAIStubServer({"choices": [{"message": {"content": ""}}]})
        openai.start()

        try:
            provider = OpenAIChatAnswerProvider(
                base_url=openai.base_url,
                api_key="test-key",
                model="gpt-4.1-mini",
                timeout_seconds=5,
            )
            prompt = build_chat_prompt(
                parse_chat_answer_request(
                    {
                        "projectId": "project-1",
                        "ownerId": "owner-1",
                        "question": "분석해줘",
                        "contexts": [],
                        "history": [],
                    }
                )
            )

            with self.assertRaises(OpenAIChatProviderError):
                provider.generate(prompt)
        finally:
            openai.stop()


class OpenAIStubServer:
    def __init__(self, response_body):
        self.response_body = response_body
        self.requests = []
        self.server = None
        self.thread = None
        self.base_url = ""

    def start(self):
        response_body = self.response_body
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length)
                requests.append(
                    {
                        "path": self.path,
                        "headers": dict(self.headers.items()),
                        "body": loads(body.decode("utf-8")),
                    }
                )

                payload = dumps(response_body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()

        if self.thread is not None:
            self.thread.join(timeout=1)
```

- [ ] **Step 2: Run OpenAI provider tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_openai_provider
```

Expected: FAIL with `ModuleNotFoundError: No module named 'documind_ai.openai_provider'`.

- [ ] **Step 3: Implement `openai_provider.py`**

Create `src/documind_ai/openai_provider.py`:

```python
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
```

- [ ] **Step 4: Update settings**

Modify `src/documind_ai/config.py`:

```python
from dataclasses import dataclass
from os import getenv
from typing import Optional


@dataclass(frozen=True)
class AppSettings:
    service_name: str
    environment: str
    host: str
    port: int
    chat_provider: str = "stub"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    timeout_seconds: int = 60
    openai_base_url: str = "https://api.openai.com"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4.1-mini"


def load_settings() -> AppSettings:
    return AppSettings(
        service_name=getenv("DOCUMIND_AI_SERVICE_NAME", "documind-ai"),
        environment=getenv("DOCUMIND_AI_ENV", "local"),
        host=getenv("DOCUMIND_AI_HOST", "0.0.0.0"),
        port=int(getenv("DOCUMIND_AI_PORT", "8001")),
        chat_provider=getenv("DOCUMIND_AI_CHAT_PROVIDER", "stub"),
        ollama_base_url=getenv("DOCUMIND_AI_OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=getenv("DOCUMIND_AI_OLLAMA_MODEL", "llama3.2"),
        timeout_seconds=int(
            getenv(
                "DOCUMIND_AI_TIMEOUT_SECONDS",
                getenv("DOCUMIND_AI_OLLAMA_TIMEOUT_SECONDS", "60"),
            )
        ),
        openai_base_url=getenv("DOCUMIND_AI_OPENAI_BASE_URL", "https://api.openai.com"),
        openai_api_key=getenv("DOCUMIND_AI_OPENAI_API_KEY"),
        openai_model=getenv("DOCUMIND_AI_OPENAI_MODEL", "gpt-4.1-mini"),
    )
```

- [ ] **Step 5: Add OpenAI provider selection**

Modify `src/documind_ai/chat_provider.py` imports:

```python
from documind_ai.openai_provider import (
    OpenAIChatAnswerProvider,
    OpenAIProviderConfigurationError,
)
```

Add branch in `select_chat_answer_provider`:

```python
if provider_name == "openai":
    if settings.openai_api_key is None:
        raise OpenAIProviderConfigurationError("OpenAI API key가 설정되지 않았습니다.")

    return OpenAIChatAnswerProvider(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout_seconds=settings.timeout_seconds,
    )
```

- [ ] **Step 6: Add provider selection tests**

Add to `tests/test_chat_provider.py`:

```python
from documind_ai.openai_provider import (
    OpenAIChatAnswerProvider,
    OpenAIProviderConfigurationError,
)

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
```

- [ ] **Step 7: Update `.env.example`**

Update `.env.example`:

```text
DOCUMIND_AI_ENV=local
DOCUMIND_AI_HOST=0.0.0.0
DOCUMIND_AI_PORT=8001
DOCUMIND_AI_SERVICE_NAME=documind-ai
DOCUMIND_AI_CHAT_PROVIDER=stub
DOCUMIND_AI_TIMEOUT_SECONDS=60
DOCUMIND_AI_OLLAMA_BASE_URL=http://localhost:11434
DOCUMIND_AI_OLLAMA_MODEL=llama3.2
DOCUMIND_AI_OPENAI_BASE_URL=https://api.openai.com
DOCUMIND_AI_OPENAI_API_KEY=
DOCUMIND_AI_OPENAI_MODEL=gpt-4.1-mini
```

- [ ] **Step 8: Run tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_openai_provider tests.test_chat_provider
PYTHONPATH=src python3 -m unittest discover -s tests
```

Expected: PASS.

- [ ] **Step 9: Commit Task 5**

Run:

```bash
git add src/documind_ai/openai_provider.py src/documind_ai/config.py src/documind_ai/chat_provider.py tests/test_openai_provider.py tests/test_chat_provider.py .env.example
git commit -m "feat: OpenAI chat provider 추가" -m "배경
최종 품질 확인과 운영 전환을 위해 OpenAI provider를 기존 AI 서비스 provider 선택 구조에 추가해야 합니다.

판단
OpenAI provider는 BuiltPrompt를 OpenAI chat completions payload로 변환하고 raw text만 반환하도록 구현했습니다. API key 누락은 설정 오류로 분리했습니다.

검증
PYTHONPATH=src python3 -m unittest tests.test_openai_provider tests.test_chat_provider 통과
PYTHONPATH=src python3 -m unittest discover -s tests 통과

남은 리스크
실제 OpenAI API 호출은 비용이 발생하므로 자동 테스트에서는 실행하지 않았습니다."
```

---

### Task 6: Error Mapping and Documentation

**Files:**
- Modify: `src/documind_ai/main.py`
- Modify: `tests/test_http_server.py`
- Modify: `README.md`
- Modify: `docs/specs/ai-provider-prompt-contract-design.md` only if implementation intentionally diverges from the design

**Interfaces:**
- Consumes:
  - `OpenAIProviderConfigurationError`
  - `OpenAIChatProviderError`
  - `OpenAIChatProviderTimeoutError`
  - `OllamaChatProviderError`
  - `OllamaChatProviderTimeoutError`
  - `ChatAnswerNormalizationError`
- Produces: HTTP status mapping for `/chat/answers`

- [ ] **Step 1: Add HTTP error mapping tests**

In `tests/test_http_server.py`, add fake errors:

```python
from documind_ai.chat_response import ChatAnswerNormalizationError
from documind_ai.openai_provider import (
    OpenAIChatProviderTimeoutError,
    OpenAIProviderConfigurationError,
)


class TimeoutChatAnswerProvider:
    def generate(self, prompt):
        raise OpenAIChatProviderTimeoutError("OpenAI 요청 시간이 초과되었습니다.")


class ConfigurationFailingChatAnswerProvider:
    def generate(self, prompt):
        raise OpenAIProviderConfigurationError("OpenAI API key가 설정되지 않았습니다.")


class NormalizationFailingChatAnswerProvider:
    def generate(self, prompt):
        raise ChatAnswerNormalizationError("provider 응답 content는 비어 있지 않아야 합니다.")
```

Add a helper to reduce duplicated server setup:

```python
def restart_server_with_provider(self, provider):
    self.server.shutdown()
    self.thread.join(timeout=1)
    self.server.server_close()

    settings = AppSettings("documind-ai-test", "test", "127.0.0.1", 0)
    self.server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        create_handler(settings, provider),
    )
    self.thread = Thread(target=self.server.serve_forever, daemon=True)
    self.thread.start()
    self.host, self.port = self.server.server_address
```

Add tests:

```python
def test_chat_answer_endpoint_maps_timeout_to_gateway_timeout(self):
    self.restart_server_with_provider(TimeoutChatAnswerProvider())

    response, body = self.post_chat_answer({"question": "분석해줘"})

    self.assertEqual(response.status, 504)
    self.assertIn("message", body)

def test_chat_answer_endpoint_maps_configuration_error_to_internal_server_error(self):
    self.restart_server_with_provider(ConfigurationFailingChatAnswerProvider())

    response, body = self.post_chat_answer({"question": "분석해줘"})

    self.assertEqual(response.status, 500)
    self.assertIn("message", body)

def test_chat_answer_endpoint_maps_normalization_error_to_bad_gateway(self):
    self.restart_server_with_provider(NormalizationFailingChatAnswerProvider())

    response, body = self.post_chat_answer({"question": "분석해줘"})

    self.assertEqual(response.status, 502)
    self.assertIn("message", body)
```

Implement `post_chat_answer` helper in the test class:

```python
def post_chat_answer(self, overrides):
    payload = {
        "projectId": "project-1",
        "ownerId": "owner-1",
        "question": "분석해줘",
        "contexts": [],
        "history": [],
    }
    payload.update(overrides)

    connection = HTTPConnection(self.host, self.port)
    connection.request(
        "POST",
        "/chat/answers",
        body=dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    response = connection.getresponse()
    body = loads(response.read().decode("utf-8"))
    connection.close()

    return response, body
```

- [ ] **Step 2: Run HTTP tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_http_server
```

Expected: FAIL because new error mapping is not implemented.

- [ ] **Step 3: Implement error mapping in `main.py`**

Add imports:

```python
from documind_ai.openai_provider import (
    OpenAIChatProviderError,
    OpenAIChatProviderTimeoutError,
    OpenAIProviderConfigurationError,
)
from documind_ai.ollama_provider import (
    OllamaChatProviderError,
    OllamaChatProviderTimeoutError,
)
from documind_ai.chat_provider import UnknownChatAnswerProviderError
```

Add exception branches:

```python
except (OpenAIProviderConfigurationError, UnknownChatAnswerProviderError) as error:
    self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": str(error)})
except (OpenAIChatProviderTimeoutError, OllamaChatProviderTimeoutError) as error:
    self.send_json(HTTPStatus.GATEWAY_TIMEOUT, {"message": str(error)})
except (OpenAIChatProviderError, OllamaChatProviderError, ChatAnswerNormalizationError) as error:
    self.send_json(HTTPStatus.BAD_GATEWAY, {"message": str(error)})
```

Place the more specific timeout/configuration branches before the broader provider error branch.

- [ ] **Step 4: Update README provider docs**

In `README.md`, update Environment block:

```text
DOCUMIND_AI_CHAT_PROVIDER=stub
DOCUMIND_AI_TIMEOUT_SECONDS=60
DOCUMIND_AI_OLLAMA_BASE_URL=http://localhost:11434
DOCUMIND_AI_OLLAMA_MODEL=llama3.2
DOCUMIND_AI_OPENAI_BASE_URL=https://api.openai.com
DOCUMIND_AI_OPENAI_API_KEY=
DOCUMIND_AI_OPENAI_MODEL=gpt-4.1-mini
```

Add OpenAI section:

````markdown
To use OpenAI for final quality checks:

```bash
DOCUMIND_AI_CHAT_PROVIDER=openai
DOCUMIND_AI_OPENAI_API_KEY=
DOCUMIND_AI_OPENAI_MODEL=gpt-4.1-mini
DOCUMIND_AI_TIMEOUT_SECONDS=60
```

Set `DOCUMIND_AI_OPENAI_API_KEY` only in the local shell or local `.env` file used for manual smoke checks.

OpenAI requests can incur cost. Keep OpenAI smoke checks manual and use `stub` or `ollama` for normal local development.
````

- [ ] **Step 5: Run full validation**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall src tests
git diff --check
```

Expected: PASS.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
git add src/documind_ai/main.py tests/test_http_server.py README.md
git commit -m "feat: AI provider 오류 매핑과 실행 문서 보강" -m "배경
Ollama와 OpenAI provider를 함께 지원하려면 설정 오류, timeout, upstream 오류를 HTTP 응답으로 구분해야 합니다.

판단
provider 설정 오류는 500, timeout은 504, provider 응답과 정규화 오류는 502로 매핑하고 README에 provider별 실행 설정을 보강했습니다.

검증
PYTHONPATH=src python3 -m unittest discover -s tests 통과
python3 -m compileall src tests 통과
git diff --check 통과

남은 리스크
실제 OpenAI smoke는 비용이 발생하므로 수동 확인으로 남겼습니다."
```

---

### Task 7: Final Integration Review

**Files:**
- Modify only if final checks reveal a mismatch:
  - `docs/specs/ai-provider-prompt-contract-design.md`
  - `README.md`
  - `.env.example`

**Interfaces:**
- Consumes: all previous task outputs
- Produces: implementation-ready branch with stable tests and docs

- [ ] **Step 1: Run final full validation**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall src tests
rg -n "answer\\(|generate\\(|DOCUMIND_AI_OLLAMA_TIMEOUT_SECONDS|DOCUMIND_AI_TIMEOUT_SECONDS|openai|ollama|stub" src tests README.md .env.example docs/specs/ai-provider-prompt-contract-design.md
git diff --check
```

Expected:

- `unittest` PASS
- `compileall` PASS
- `git diff --check` no output
- `rg` output shows `generate(` as provider protocol and no remaining production call path that uses `provider.answer(request)`
- `DOCUMIND_AI_OLLAMA_TIMEOUT_SECONDS` appears only as documented fallback or compatibility reference

- [ ] **Step 2: Verify no sensitive value is committed**

Run:

```bash
rg -n "sk-|OPENAI_API_KEY=.+\\S|Bearer [A-Za-z0-9]" .
```

Expected: no real secret values. `.env.example` may contain an empty `DOCUMIND_AI_OPENAI_API_KEY=`.

- [ ] **Step 3: Commit any final doc alignment**

If no files changed, skip this commit.

If files changed, run:

```bash
git add README.md .env.example docs/specs/ai-provider-prompt-contract-design.md
git commit -m "docs: AI provider 실행 기준 정리" -m "배경
구현 결과와 설계 문서 및 실행 문서의 표현을 맞춰야 합니다.

판단
provider 설정과 수동 smoke 기준을 현재 구현과 일치하도록 정리했습니다.

검증
PYTHONPATH=src python3 -m unittest discover -s tests 통과
python3 -m compileall src tests 통과
git diff --check 통과

남은 리스크
문서 정렬만 포함되어 실제 OpenAI 호출은 실행하지 않았습니다."
```

- [ ] **Step 4: Prepare PR**

Use PR title:

```text
feat: AI provider prompt contract 구현
```

Use PR body sections:

```markdown
## 연결 이슈

Refs the GitHub issue created for the implementation task.

## 작업 배경

로컬 Ollama 개발과 OpenAI 품질 확인을 모두 지원하기 위해 AI provider prompt contract를 구현합니다.

## 변경 사항

- PromptBuilder 추가
- ResponseNormalizer 추가
- provider protocol을 BuiltPrompt 기반으로 전환
- Ollama provider 책임을 모델 호출로 제한
- OpenAI provider 추가
- provider 오류 HTTP status mapping 추가
- README와 .env.example 실행 설정 보강

## 검증 결과

- PYTHONPATH=src python3 -m unittest discover -s tests 통과
- python3 -m compileall src tests 통과
- git diff --check 통과

## 남은 리스크

실제 OpenAI smoke는 비용이 발생하므로 자동 검증에서 제외했습니다.
```
