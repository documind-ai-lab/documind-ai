from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.chat_response import (
    ChatAnswerNormalizationError,
    normalize_chat_answer,
)


class ChatResponseTest(TestCase):
    def test_returns_empty_sources_without_contexts(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "분석해줘",
                "contexts": [],
                "history": [],
            }
        )

        answer = normalize_chat_answer("문서가 아직 없습니다.", request)

        self.assertEqual(answer, {"content": "문서가 아직 없습니다.", "sources": []})

    def test_builds_source_from_first_context(self):
        request = parse_chat_answer_request(
            {
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
        )

        answer = normalize_chat_answer("견적서 기준 검토 결과입니다. [1]", request)

        self.assertEqual(answer["content"], "견적서 기준 검토 결과입니다. [1]")
        self.assertEqual(
            answer["sources"],
            [
                {
                    "documentId": "document-1",
                    "title": "견적서.txt",
                    "quote": "총액은 1000만원이며 납기는 별도 협의입니다.",
                    "relevance": 0.75,
                }
            ],
        )

    def test_adds_source_marker_when_context_exists(self):
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

        answer = normalize_chat_answer("견적서 기준 검토 결과입니다.", request)

        self.assertEqual(answer["content"], "견적서 기준 검토 결과입니다.\n\n[1]")

    def test_rejects_empty_raw_text(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "분석해줘",
                "contexts": [],
                "history": [],
            }
        )

        with self.assertRaises(ChatAnswerNormalizationError):
            normalize_chat_answer("   ", request)
