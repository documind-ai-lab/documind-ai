# documind-ai

DocuMind AI service.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
PYTHONPATH=src python -m documind_ai.main
```

The default server address is `http://localhost:8001`.

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
    "history": []
  }'
```

Response:

```json
{
  "content": "업로드된 문서 기준으로 질문을 검토했습니다. [1]\n\n질문: 견적서 리스크를 알려줘\n\n핵심 근거: 총액은 1000만원이며 납기는 별도 협의입니다.",
  "sources": [
    {
      "documentId": "document-1",
      "title": "견적서.txt",
      "quote": "총액은 1000만원이며 납기는 별도 협의입니다.",
      "relevance": 0.85
    }
  ]
}
```

## Scope

This first service skeleton uses only the Python standard library. Frameworks such as FastAPI and LLM providers such as OpenAI, Gemini, or Ollama will be added in separate issues after the dependency decision is explicit.
