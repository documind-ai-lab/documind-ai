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

## Scope

This first service skeleton uses only the Python standard library. Frameworks such as FastAPI and LLM providers such as OpenAI, Gemini, or Ollama will be added in separate issues after the dependency decision is explicit.
