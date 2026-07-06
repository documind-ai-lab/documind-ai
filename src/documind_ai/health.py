from documind_ai.config import AppSettings


def build_health_response(settings: AppSettings) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }
