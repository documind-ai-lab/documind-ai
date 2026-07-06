from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class AppSettings:
    service_name: str
    environment: str
    host: str
    port: int


def load_settings() -> AppSettings:
    return AppSettings(
        service_name=getenv("DOCUMIND_AI_SERVICE_NAME", "documind-ai"),
        environment=getenv("DOCUMIND_AI_ENV", "local"),
        host=getenv("DOCUMIND_AI_HOST", "0.0.0.0"),
        port=int(getenv("DOCUMIND_AI_PORT", "8001")),
    )
