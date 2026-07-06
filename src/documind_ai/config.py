from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class AppSettings:
    service_name: str
    environment: str
    host: str
    port: int
    chat_provider: str = "stub"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: int = 60


def load_settings() -> AppSettings:
    return AppSettings(
        service_name=getenv("DOCUMIND_AI_SERVICE_NAME", "documind-ai"),
        environment=getenv("DOCUMIND_AI_ENV", "local"),
        host=getenv("DOCUMIND_AI_HOST", "0.0.0.0"),
        port=int(getenv("DOCUMIND_AI_PORT", "8001")),
        chat_provider=getenv("DOCUMIND_AI_CHAT_PROVIDER", "stub"),
        ollama_base_url=getenv("DOCUMIND_AI_OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=getenv("DOCUMIND_AI_OLLAMA_MODEL", "llama3.2"),
        ollama_timeout_seconds=int(getenv("DOCUMIND_AI_OLLAMA_TIMEOUT_SECONDS", "60")),
    )
