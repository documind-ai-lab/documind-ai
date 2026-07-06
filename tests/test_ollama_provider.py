from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps, loads
from threading import Thread
from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.ollama_provider import (
    OllamaChatAnswerProvider,
    OllamaChatProviderError,
    build_ollama_messages,
)


class OllamaProviderTest(TestCase):
    def test_builds_ollama_messages_with_contexts_and_history(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "견적서 리스크를 알려줘",
                "contexts": [
                    {
                        "documentId": "document-1",
                        "title": "견적서.txt",
                        "content": "총액은 1000만원입니다.",
                    }
                ],
                "history": [{"role": "USER", "content": "이전 질문"}],
            }
        )

        messages = build_ollama_messages(request)

        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1], {"role": "user", "content": "이전 질문"})
        self.assertEqual(messages[2]["role"], "user")
        self.assertIn("질문:", messages[2]["content"])
        self.assertIn("[1] 문서명: 견적서.txt", messages[2]["content"])
        self.assertIn("총액은 1000만원입니다.", messages[2]["content"])

    def test_calls_ollama_chat_api_and_returns_chat_answer(self):
        ollama = OllamaStubServer(
            {
                "message": {
                    "role": "assistant",
                    "content": "견적서 기준 검토 결과입니다. [1]",
                },
                "done": True,
            }
        )
        ollama.start()

        try:
            provider = OllamaChatAnswerProvider(
                base_url=ollama.base_url,
                model="llama3.2",
                timeout_seconds=5,
            )
            request = parse_chat_answer_request(
                {
                    "projectId": "project-1",
                    "ownerId": "owner-1",
                    "question": "견적서 리스크를 알려줘",
                    "contexts": [
                        {
                            "documentId": "document-1",
                            "title": "견적서.txt",
                            "content": "총액은 1000만원입니다.",
                        }
                    ],
                    "history": [],
                }
            )

            answer = provider.answer(request)

            self.assertEqual(ollama.requests[0]["path"], "/api/chat")
            self.assertEqual(ollama.requests[0]["body"]["model"], "llama3.2")
            self.assertEqual(ollama.requests[0]["body"]["stream"], False)
            self.assertEqual(ollama.requests[0]["body"]["messages"][-1]["role"], "user")
            self.assertEqual(answer["content"], "견적서 기준 검토 결과입니다. [1]")
            self.assertEqual(
                answer["sources"],
                [
                    {
                        "documentId": "document-1",
                        "title": "견적서.txt",
                        "quote": "총액은 1000만원입니다.",
                        "relevance": 0.75,
                    }
                ],
            )
        finally:
            ollama.stop()

    def test_rejects_invalid_ollama_response_shape(self):
        ollama = OllamaStubServer({"message": {"role": "assistant", "content": ""}})
        ollama.start()

        try:
            provider = OllamaChatAnswerProvider(
                base_url=ollama.base_url,
                model="llama3.2",
                timeout_seconds=5,
            )
            request = parse_chat_answer_request(
                {
                    "projectId": "project-1",
                    "ownerId": "owner-1",
                    "question": "분석해줘",
                    "contexts": [],
                    "history": [],
                }
            )

            with self.assertRaises(OllamaChatProviderError):
                provider.answer(request)
        finally:
            ollama.stop()

    def test_rejects_invalid_ollama_json_response(self):
        ollama = OllamaStubServer(response_text="{")
        ollama.start()

        try:
            provider = OllamaChatAnswerProvider(
                base_url=ollama.base_url,
                model="llama3.2",
                timeout_seconds=5,
            )
            request = parse_chat_answer_request(
                {
                    "projectId": "project-1",
                    "ownerId": "owner-1",
                    "question": "분석해줘",
                    "contexts": [],
                    "history": [],
                }
            )

            with self.assertRaises(OllamaChatProviderError) as error:
                provider.answer(request)

            self.assertEqual(str(error.exception), "Ollama 응답은 JSON이어야 합니다.")
        finally:
            ollama.stop()


class OllamaStubServer:
    def __init__(self, response_body=None, response_text=None):
        self.response_body = response_body
        self.response_text = response_text
        self.requests = []
        self.server = None
        self.thread = None
        self.base_url = ""

    def start(self):
        response_body = self.response_body
        response_text = self.response_text
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length)
                requests.append(
                    {
                        "path": self.path,
                        "body": loads(body.decode("utf-8")),
                    }
                )

                response_payload = (
                    response_text
                    if response_text is not None
                    else dumps(response_body, ensure_ascii=False)
                )
                payload = response_payload.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()

        if self.thread is not None:
            self.thread.join(timeout=1)
