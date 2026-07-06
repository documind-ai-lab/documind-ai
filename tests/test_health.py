from unittest import TestCase

from documind_ai.config import AppSettings
from documind_ai.health import build_health_response


class HealthResponseTest(TestCase):
    def test_build_health_response(self):
        settings = AppSettings("documind-ai-test", "test", "127.0.0.1", 8001)

        self.assertEqual(
            build_health_response(settings),
            {
                "status": "ok",
                "service": "documind-ai-test",
                "environment": "test",
            },
        )
