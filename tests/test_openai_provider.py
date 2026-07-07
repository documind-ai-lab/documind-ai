from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps, loads
from threading import Thread
from unittest import TestCase

from documind_ai.chat_prompt import BuiltPrompt, BuiltPromptMessage
from documind_ai.openai_provider import (
    OpenAIChatAnswerProvider,
    OpenAIChatProviderError,
    OpenAIProviderConfigurationError,
)


class OpenAIProviderTest(TestCase):
    def test_calls_openai_chat_completions_api(self):
        openai = OpenAIStubServer(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "견적서 기준 검토 결과입니다. [1]",
                        }
                    }
                ]
            }
        )
        openai.start()

        try:
            provider = OpenAIChatAnswerProvider(
                base_url=openai.base_url,
                api_key="test-key",
                model="gpt-4.1-mini",
                timeout_seconds=5,
            )
            prompt = BuiltPrompt(
                messages=[
                    BuiltPromptMessage(role="system", content="system"),
                    BuiltPromptMessage(role="user", content="question"),
                ]
            )

            answer = provider.generate(prompt)

            self.assertEqual(openai.requests[0]["path"], "/v1/chat/completions")
            self.assertEqual(openai.requests[0]["body"]["model"], "gpt-4.1-mini")
            self.assertEqual(openai.requests[0]["body"]["messages"][1]["role"], "user")
            self.assertTrue(openai.requests[0]["headers"]["Authorization"].startswith("Bearer "))
            self.assertEqual(answer, "견적서 기준 검토 결과입니다. [1]")
        finally:
            openai.stop()

    def test_rejects_empty_api_key(self):
        with self.assertRaises(OpenAIProviderConfigurationError):
            OpenAIChatAnswerProvider(
                base_url="http://127.0.0.1:1",
                api_key="",
                model="gpt-4.1-mini",
                timeout_seconds=5,
            )

    def test_rejects_invalid_openai_response_shape(self):
        openai = OpenAIStubServer({"choices": [{"message": {"content": ""}}]})
        openai.start()

        try:
            provider = OpenAIChatAnswerProvider(
                base_url=openai.base_url,
                api_key="test-key",
                model="gpt-4.1-mini",
                timeout_seconds=5,
            )
            prompt = BuiltPrompt(messages=[BuiltPromptMessage(role="user", content="question")])

            with self.assertRaises(OpenAIChatProviderError):
                provider.generate(prompt)
        finally:
            openai.stop()

    def test_rejects_invalid_openai_json_response(self):
        openai = OpenAIStubServer(response_text="{")
        openai.start()

        try:
            provider = OpenAIChatAnswerProvider(
                base_url=openai.base_url,
                api_key="test-key",
                model="gpt-4.1-mini",
                timeout_seconds=5,
            )
            prompt = BuiltPrompt(messages=[BuiltPromptMessage(role="user", content="question")])

            with self.assertRaises(OpenAIChatProviderError):
                provider.generate(prompt)
        finally:
            openai.stop()


class OpenAIStubServer:
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
                        "headers": dict(self.headers.items()),
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
