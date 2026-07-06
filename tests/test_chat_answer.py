from unittest import TestCase

from documind_ai.chat_answer import (
    ChatAnswerRequestError,
    generate_chat_answer,
    parse_chat_answer_request,
)


class ChatAnswerTest(TestCase):
    def test_generate_answer_without_contexts(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "분석해줘",
                "contexts": [],
                "history": [],
            }
        )

        answer = generate_chat_answer(request)

        self.assertIn("분석 가능한 문서 텍스트가 아직 없습니다", answer["content"])
        self.assertEqual(answer["sources"], [])

    def test_generate_answer_with_primary_context_source(self):
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

        answer = generate_chat_answer(request)

        self.assertIn("[1]", answer["content"])
        self.assertEqual(
            answer["sources"],
            [
                {
                    "documentId": "document-1",
                    "title": "견적서.txt",
                    "quote": "총액은 1000만원이며 납기는 별도 협의입니다.",
                    "relevance": 0.85,
                }
            ],
        )

    def test_parse_request_rejects_missing_question(self):
        with self.assertRaises(ChatAnswerRequestError):
            parse_chat_answer_request(
                {
                    "projectId": "project-1",
                    "ownerId": "owner-1",
                    "contexts": [],
                    "history": [],
                }
            )
