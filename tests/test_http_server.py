from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from json import dumps, loads
from threading import Thread
from unittest import TestCase

from documind_ai.chat_response import ChatAnswerNormalizationError
from documind_ai.config import AppSettings
from documind_ai.main import create_handler
from documind_ai.ollama_provider import OllamaChatProviderError
from documind_ai.openai_provider import (
    OpenAIChatProviderTimeoutError,
    OpenAIProviderConfigurationError,
)


class FakeChatAnswerProvider:
    def generate(self, prompt):
        return "provider answer"


class FailingChatAnswerProvider:
    def generate(self, prompt):
        raise OllamaChatProviderError("Ollama 연결 실패: refused")


class TimeoutChatAnswerProvider:
    def generate(self, prompt):
        raise OpenAIChatProviderTimeoutError("OpenAI 요청 시간이 초과되었습니다.")


class ConfigurationFailingChatAnswerProvider:
    def generate(self, prompt):
        raise OpenAIProviderConfigurationError("OpenAI API key가 설정되지 않았습니다.")


class NormalizationFailingChatAnswerProvider:
    def generate(self, prompt):
        raise ChatAnswerNormalizationError("provider 응답 content는 비어 있지 않아야 합니다.")


class HttpServerTest(TestCase):
    def setUp(self):
        settings = AppSettings("documind-ai-test", "test", "127.0.0.1", 0)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(settings))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=1)
        self.server.server_close()

    def test_health_endpoint(self):
        connection = HTTPConnection(self.host, self.port)

        connection.request("GET", "/health")
        response = connection.getresponse()
        body = loads(response.read().decode("utf-8"))
        connection.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(
            body,
            {
                "status": "ok",
                "service": "documind-ai-test",
                "environment": "test",
            },
        )

    def test_chat_answer_endpoint(self):
        response, body = self.post_chat_answer(
            {
                "question": "견적서 리스크를 알려줘",
                "contexts": [
                    {
                        "documentId": "document-1",
                        "title": "견적서.txt",
                        "content": "총액은 1000만원이며 납기는 별도 협의입니다.",
                    }
                ],
            }
        )

        self.assertEqual(response.status, 200)
        self.assertIn("[1]", body["content"])
        self.assertEqual(body["sources"][0]["documentId"], "document-1")

    def test_chat_answer_endpoint_without_contexts_has_no_source_marker(self):
        response, body = self.post_chat_answer({"question": "분석해줘"})

        self.assertEqual(response.status, 200)
        self.assertNotIn("[1]", body["content"])
        self.assertEqual(body["sources"], [])

    def test_chat_answer_endpoint_uses_injected_provider(self):
        self.restart_server_with_provider(FakeChatAnswerProvider())

        response, body = self.post_chat_answer({"question": "분석해줘"})

        self.assertEqual(response.status, 200)
        self.assertEqual(body["content"], "provider answer")
        self.assertEqual(body["sources"], [])

    def test_chat_answer_endpoint_rejects_invalid_json(self):
        connection = HTTPConnection(self.host, self.port)

        connection.request(
            "POST",
            "/chat/answers",
            body="{",
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = loads(response.read().decode("utf-8"))
        connection.close()

        self.assertEqual(response.status, 400)
        self.assertIn("message", body)

    def test_chat_answer_endpoint_maps_provider_error_to_bad_gateway(self):
        self.restart_server_with_provider(FailingChatAnswerProvider())

        response, body = self.post_chat_answer({"question": "분석해줘"})

        self.assertEqual(response.status, 502)
        self.assertEqual(body["message"], "Ollama 연결 실패: refused")

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

    def test_chat_answer_endpoint_maps_provider_selection_error_to_internal_server_error(self):
        self.server.shutdown()
        self.thread.join(timeout=1)
        self.server.server_close()

        settings = AppSettings(
            "documind-ai-test",
            "test",
            "127.0.0.1",
            0,
            chat_provider="openai",
            openai_api_key=None,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(settings))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

        response, body = self.post_chat_answer({"question": "분석해줘"})

        self.assertEqual(response.status, 500)
        self.assertEqual(body["message"], "OpenAI API key가 설정되지 않았습니다.")

    def test_chat_answer_endpoint_maps_normalization_error_to_bad_gateway(self):
        self.restart_server_with_provider(NormalizationFailingChatAnswerProvider())

        response, body = self.post_chat_answer({"question": "분석해줘"})

        self.assertEqual(response.status, 502)
        self.assertIn("message", body)

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
