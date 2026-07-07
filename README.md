# documind-ai

DocuMind AI service.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
PYTHONPATH=src python -m documind_ai.main
```

The default server address is `http://localhost:8001`.

Environment:

```bash
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

## Health Check

```bash
curl http://localhost:8001/health
```

Response:

```json
{
  "status": "ok",
  "service": "documind-ai",
  "environment": "local"
}
```

## Chat Answer Contract

```bash
curl -X POST http://localhost:8001/chat/answers \
  -H "Content-Type: application/json" \
  -d '{
    "projectId": "project-1",
    "ownerId": "owner-1",
    "question": "견적서 리스크를 알려줘",
    "contexts": [
      {
        "documentId": "document-1",
        "title": "견적서.txt",
        "content": "총액은 1000만원이며 납기는 별도 협의입니다."
      }
    ],
    "history": [
      {
        "role": "USER",
        "content": "이 견적서 먼저 요약해줘"
      },
      {
        "role": "ASSISTANT",
        "content": "견적서 핵심 내용을 요약했습니다. [1]"
      }
    ]
  }'
```

Request fields:

- `projectId`, `ownerId`, `question` are required non-empty strings.
- `contexts` is optional. Each context item requires `documentId`, `title`, and `content`.
- `history` is optional. Each history item requires `role` and `content`.
- `history[].role` accepts `USER` or `ASSISTANT`. Input is normalized for surrounding whitespace and case.

Response:

```json
{
  "content": "업로드된 문서 기준으로 질문을 검토했습니다.\n\n[1]",
  "sources": [
    {
      "documentId": "document-1",
      "title": "견적서.txt",
      "quote": "총액은 1000만원이며 납기는 별도 협의입니다.",
      "relevance": 0.75
    }
  ]
}
```

Response fields:

- `content` is a non-empty answer string.
- `sources` is an array of document evidence used in the answer.
- `sources[].relevance` is a number from `0` to `1`, or `null` when not calculated.

## Scope

This service skeleton uses only the Python standard library.

`DOCUMIND_AI_CHAT_PROVIDER=stub` keeps the deterministic local answer provider.

To use a local Ollama server:

```bash
DOCUMIND_AI_CHAT_PROVIDER=ollama
DOCUMIND_AI_OLLAMA_BASE_URL=http://localhost:11434
DOCUMIND_AI_OLLAMA_MODEL=llama3.2
DOCUMIND_AI_TIMEOUT_SECONDS=60
```

The Ollama provider calls `POST /api/chat` with `stream: false` and returns raw answer text. The HTTP endpoint normalizes the result into the existing `/chat/answers` shape.

To use OpenAI for final quality checks:

```bash
DOCUMIND_AI_CHAT_PROVIDER=openai
DOCUMIND_AI_OPENAI_API_KEY=
DOCUMIND_AI_OPENAI_MODEL=gpt-4.1-mini
DOCUMIND_AI_TIMEOUT_SECONDS=60
```

Set `DOCUMIND_AI_OPENAI_API_KEY` only in the local shell or local `.env` file used for manual smoke checks.

OpenAI requests can incur cost. Keep OpenAI smoke checks manual and use `stub` or `ollama` for normal local development.

Frameworks such as FastAPI or provider adapters such as Gemini will be added in separate issues after the dependency decision is explicit.
