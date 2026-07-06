from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from json import dumps, loads
from threading import Thread
from unittest import TestCase

from documind_ai.config import AppSettings
from documind_ai.main import create_handler
from documind_ai.ollama_provider import OllamaChatProviderError


class FakeChatAnswerProvider:
    def answer(self, request):
        return {
            "content": f"provider answer: {request.question}",
            "sources": [],
        }


class FailingChatAnswerProvider:
    def answer(self, request):
        raise OllamaChatProviderError("Ollama 연결 실패: refused")


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
        connection = HTTPConnection(self.host, self.port)
        payload = {
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

        connection.request(
            "POST",
            "/chat/answers",
            body=dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = loads(response.read().decode("utf-8"))
        connection.close()

        self.assertEqual(response.status, 200)
        self.assertIn("[1]", body["content"])
        self.assertEqual(body["sources"][0]["documentId"], "document-1")

    def test_chat_answer_endpoint_uses_injected_provider(self):
        self.server.shutdown()
        self.thread.join(timeout=1)
        self.server.server_close()

        settings = AppSettings("documind-ai-test", "test", "127.0.0.1", 0)
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            create_handler(settings, FakeChatAnswerProvider()),
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address
        connection = HTTPConnection(self.host, self.port)

        connection.request(
            "POST",
            "/chat/answers",
            body=dumps(
                {
                    "projectId": "project-1",
                    "ownerId": "owner-1",
                    "question": "분석해줘",
                    "contexts": [],
                    "history": [],
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = loads(response.read().decode("utf-8"))
        connection.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(body["content"], "provider answer: 분석해줘")
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
        self.server.shutdown()
        self.thread.join(timeout=1)
        self.server.server_close()

        settings = AppSettings("documind-ai-test", "test", "127.0.0.1", 0)
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            create_handler(settings, FailingChatAnswerProvider()),
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address
        connection = HTTPConnection(self.host, self.port)

        connection.request(
            "POST",
            "/chat/answers",
            body=dumps(
                {
                    "projectId": "project-1",
                    "ownerId": "owner-1",
                    "question": "분석해줘",
                    "contexts": [],
                    "history": [],
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = loads(response.read().decode("utf-8"))
        connection.close()

        self.assertEqual(response.status, 502)
        self.assertEqual(body["message"], "Ollama 연결 실패: refused")
