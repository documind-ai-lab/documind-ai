# AI Provider Prompt Contract 설계

## 배경

`documind-ai`는 현재 `/chat/answers` 계약, deterministic `stub` provider, 로컬 개발용 `ollama` provider 선택 구조를 갖고 있다. 다음 단계에서는 로컬 Ollama로 개발 비용을 낮추면서, 최종 품질 확인이나 운영 전환 시 OpenAI provider를 사용할 수 있어야 한다.

이 설계의 목표는 provider를 추가하는 것 자체가 아니라, provider가 바뀌어도 prompt 정책과 응답 shape가 흔들리지 않는 내부 계약을 정의하는 것이다.

## 목표

- `stub`, `ollama`, `openai` provider를 같은 흐름에서 선택할 수 있게 한다.
- provider가 prompt를 직접 조립하지 않도록 공통 prompt builder 책임을 분리한다.
- provider 응답을 기존 `/chat/answers` 응답 shape인 `{ content, sources }`로 정규화한다.
- sources metadata는 모델이 직접 생성하지 않고 request `contexts` 기준으로 만든다.
- 로컬 개발은 Ollama, 계약 테스트는 stub, 최종 품질 확인은 OpenAI를 사용할 수 있게 한다.

## 범위

포함 범위:

- `documind-ai` 내부 provider 구조 설계
- 공통 prompt contract 설계
- provider 응답 정규화 기준
- 환경변수 설정 기준
- 오류 처리 기준
- 테스트 기준

제외 범위:

- embedding 생성
- vector search
- chunking과 reranking
- streaming 응답
- 자동 provider fallback
- 백엔드 Chat API 응답 shape 변경
- 클라이언트 UI 변경

## Architecture

전체 호출 흐름은 기존 백엔드와 클라이언트 계약을 유지한다.

```text
client
  -> backend Chat API
    -> documind-ai /chat/answers
      -> parse_chat_answer_request
      -> build_chat_prompt
      -> selected provider
          - stub
          - ollama
          - openai
      -> normalize_chat_answer
      -> { content, sources }
```

`documind-ai`는 HTTP 요청을 검증한 뒤 공통 prompt를 만들고, 선택된 provider를 호출한다. provider는 모델 호출과 raw text 반환만 담당한다. 최종 응답은 `normalize_chat_answer`가 request context를 기준으로 만든다.

## 설계 단위

### `parse_chat_answer_request`

현재 역할을 유지한다.

- HTTP JSON payload 검증
- `projectId`, `ownerId`, `question` 필수 문자열 검증
- `contexts[].documentId`, `contexts[].title`, `contexts[].content` 검증
- `history[].role`을 `USER | ASSISTANT`로 검증
- provider와 무관한 입력 계약 유지

### `build_chat_prompt`

새로 분리할 핵심 함수다.

입력:

- `ChatAnswerRequest`

출력:

- `BuiltPrompt`

책임:

- system prompt 생성
- conversation history message 생성
- document context message 생성
- user question message 생성
- source citation instruction 포함
- risk wording instruction 포함

provider는 `BuiltPrompt`를 받아 provider별 payload로 변환한다. provider가 request를 직접 해석해 prompt를 조립하지 않는다.

### `BuiltPrompt`

provider 공통 prompt 표현이다.

예상 구조:

```python
@dataclass(frozen=True)
class BuiltPromptMessage:
    role: str
    content: str


@dataclass(frozen=True)
class BuiltPrompt:
    messages: list[BuiltPromptMessage]
```

role은 provider 공통 표현인 `system`, `user`, `assistant`를 사용한다. OpenAI와 Ollama 모두 이 구조를 각자 payload로 변환한다.

### `ChatAnswerProvider`

provider protocol은 모델 호출 경계다.

예상 구조:

```python
class ChatAnswerProvider(Protocol):
    def generate(self, prompt: BuiltPrompt) -> str:
        ...
```

provider는 raw answer text만 반환한다. provider가 `{ content, sources }`를 만들지 않는다.

### `StubChatAnswerProvider`

테스트와 계약 확인용 provider다.

- 모델 호출 없음
- deterministic text 반환
- 기본 자동 테스트에서 사용
- provider 선택과 endpoint 흐름 검증에 사용

### `OllamaChatAnswerProvider`

로컬 개발용 provider다.

- `POST {DOCUMIND_AI_OLLAMA_BASE_URL}/api/chat` 호출
- `stream: false` 사용
- `BuiltPrompt.messages`를 Ollama chat messages로 변환
- timeout, HTTP error, JSON parse error, empty content를 provider 오류로 변환

### `OpenAIChatAnswerProvider`

운영 전환과 최종 품질 확인용 provider다.

- OpenAI API key와 model 설정을 사용
- `BuiltPrompt.messages`를 OpenAI request payload로 변환
- streaming은 1차 범위에서 제외
- 실제 OpenAI 호출은 비용이 발생하므로 기본 자동 테스트에서 제외

### `normalize_chat_answer`

provider raw answer text를 `/chat/answers` 응답 shape로 변환한다.

입력:

- raw answer text
- `ChatAnswerRequest`

출력:

```python
{
    "content": "...",
    "sources": [...]
}
```

정책:

- `content`는 비어 있지 않은 문자열이어야 한다.
- `contexts`가 없으면 `sources`는 빈 배열이다.
- `contexts`가 있으면 request context 기준으로 source를 만든다.
- 모델이 만든 documentId, title, relevance는 신뢰하지 않는다.
- 답변에 `[1]`이 없고 context가 있으면 `[1]`을 보강한다.
- 1차 relevance는 고정값 또는 `null` 중 하나로 제한한다.

## Prompt Contract

system prompt에는 다음 정책을 포함한다.

- 한국어 업무 문서 분석 assistant로 답변한다.
- 제공된 문서 근거를 우선 사용한다.
- 문서 근거가 있으면 `[1]`, `[2]` 형식의 출처 번호를 사용한다.
- 문서에 없는 내용은 추측하지 않는다.
- 법령, 규정, 리스크는 확정 판단이 아니라 “검토 후보”로 표현한다.
- 답변은 실무자가 바로 검토할 수 있도록 간결하게 작성한다.

context prompt는 다음 형식으로 구성한다.

```text
[1] 문서명: 견적서.txt
문서 ID: document-1
내용:
...
```

history prompt는 request `history` 순서를 유지한다.

- `USER` -> `user`
- `ASSISTANT` -> `assistant`

마지막 message는 현재 사용자 질문이다.

## Data Flow

1. `/chat/answers`가 HTTP 요청을 받는다.
2. `parse_chat_answer_request(payload)`가 request를 검증한다.
3. `build_chat_prompt(request)`가 provider 공통 prompt를 만든다.
4. `select_chat_answer_provider(settings)`가 provider를 선택한다.
5. provider가 `generate(prompt)`로 raw answer text를 반환한다.
6. `normalize_chat_answer(raw_text, request)`가 `{ content, sources }`를 만든다.
7. HTTP endpoint가 기존 `/chat/answers` shape로 응답한다.
8. 백엔드는 기존처럼 `userMessage`, `assistantMessage`를 저장하고 클라이언트에 반환한다.

## 환경변수

공통:

```text
DOCUMIND_AI_CHAT_PROVIDER=stub|ollama|openai
DOCUMIND_AI_TIMEOUT_SECONDS=60
```

Ollama:

```text
DOCUMIND_AI_OLLAMA_BASE_URL=http://localhost:11434
DOCUMIND_AI_OLLAMA_MODEL=llama3.2
```

OpenAI:

```text
DOCUMIND_AI_OPENAI_API_KEY=
DOCUMIND_AI_OPENAI_MODEL=gpt-4.1-mini
```

실제 API key는 로컬 shell 또는 로컬 `.env`에만 설정하고 저장소 문서나 테스트 코드에는 남기지 않는다.

기존 `DOCUMIND_AI_OLLAMA_TIMEOUT_SECONDS`는 `DOCUMIND_AI_TIMEOUT_SECONDS`로 통합하는 방향을 우선한다. 하위 호환이 필요하면 기존 값을 fallback으로 읽을 수 있다.

## Error Handling

### 요청 검증 실패

원인:

- JSON object가 아님
- 필수 문자열 누락
- `contexts` 형식 오류
- `history.role`이 `USER | ASSISTANT`가 아님

처리:

- `ChatAnswerRequestError`
- HTTP `400`

### Provider 설정 오류

원인:

- 지원하지 않는 provider 이름
- `openai` provider 선택 시 API key 없음
- model 설정 누락

처리:

- `ProviderConfigurationError`
- HTTP `500`

### Provider 호출 실패

원인:

- Ollama 서버 미실행
- OpenAI API 연결 실패
- provider timeout
- provider 응답 JSON parse 실패
- provider 응답 content 누락

처리:

- timeout은 HTTP `504`
- upstream 연결 또는 응답 오류는 HTTP `502`

### 응답 정규화 실패

원인:

- provider raw answer text가 비어 있음
- 최종 `content` 생성 불가

처리:

- `ChatAnswerNormalizationError`
- HTTP `502`

### Fallback 정책

자동 fallback은 1차 범위에서 제외한다.

예를 들어 OpenAI 실패 시 Ollama로 자동 전환하지 않는다. 어떤 provider가 답변했는지 추적 가능해야 하고, 비용과 품질 판단이 섞이면 안 되기 때문이다.

### 로그 원칙

- API key, 내부 token, raw Authorization header는 로그에 남기지 않는다.
- 문서 원문 전체를 로그에 남기지 않는다.
- provider 이름, model, 실패 유형, status code 정도만 남긴다.
- raw provider 응답 전체를 외부 응답에 노출하지 않는다.

## Testing

### Prompt Builder 단위 테스트

- context가 없을 때 질문이 포함된다.
- context가 있을 때 `[1]`, `[2]` 문서 근거가 포함된다.
- history 순서가 유지된다.
- system prompt에 핵심 정책이 포함된다.
- risk wording instruction이 포함된다.

### Response Normalizer 단위 테스트

- context가 없으면 `sources: []`를 반환한다.
- context가 있으면 source를 생성한다.
- 답변에 `[1]`이 없으면 보강한다.
- source documentId와 title은 request context에서 가져온다.
- relevance는 `0~1` number 또는 `null`만 허용한다.

### Provider 선택 테스트

- `DOCUMIND_AI_CHAT_PROVIDER=stub`
- `DOCUMIND_AI_CHAT_PROVIDER=ollama`
- `DOCUMIND_AI_CHAT_PROVIDER=openai`
- 알 수 없는 provider는 설정 오류
- OpenAI provider에서 API key가 없으면 설정 오류

### Ollama Provider 테스트

실제 Ollama 서버를 호출하지 않는다. HTTP 호출 경계를 fake 처리한다.

- `/api/chat` payload shape 검증
- `stream: false` 검증
- `message.content` 파싱 검증
- timeout, HTTP error, JSON parse error 처리 검증

### OpenAI Provider 테스트

실제 OpenAI API를 호출하지 않는다. HTTP 호출 경계를 fake 처리한다.

- Authorization header 구성 검증
- model과 messages payload 검증
- 정상 응답 text 추출 검증
- empty response와 error response 처리 검증

### HTTP Endpoint 테스트

- `/chat/answers` stub provider 정상 응답
- provider fake 정상 응답
- request validation 실패
- provider 실패 시 HTTP status mapping

### 수동 Smoke 테스트

로컬 개발:

```text
DOCUMIND_AI_CHAT_PROVIDER=stub
DOCUMIND_AI_CHAT_PROVIDER=ollama
```

최종 품질 확인:

```text
DOCUMIND_AI_CHAT_PROVIDER=openai
```

OpenAI smoke는 비용이 발생하므로 기본 자동 테스트에는 포함하지 않는다. 명시적인 수동 명령으로만 실행한다.

## 완료 기준

- 공통 prompt builder가 provider별 prompt 중복을 제거한다.
- provider는 모델 호출만 담당한다.
- OpenAI provider가 추가되어도 백엔드와 클라이언트 계약은 변경하지 않는다.
- `/chat/answers` 응답 shape는 기존 `{ content, sources }`를 유지한다.
- 오류 종류와 HTTP status mapping이 테스트로 검증된다.
