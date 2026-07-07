from unittest import TestCase

from documind_ai.chat_answer import parse_chat_answer_request
from documind_ai.chat_prompt import build_chat_prompt


class ChatPromptTest(TestCase):
    def test_builds_prompt_without_contexts(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "분석해줘",
                "contexts": [],
                "history": [],
            }
        )

        prompt = build_chat_prompt(request)

        self.assertEqual(prompt.messages[0].role, "system")
        self.assertIn("한국어 업무 문서 분석", prompt.messages[0].content)
        self.assertIn("추측하지", prompt.messages[0].content)
        self.assertEqual(prompt.messages[-1].role, "user")
        self.assertEqual(prompt.messages[-1].content, "질문:\n분석해줘")

    def test_builds_prompt_with_contexts_and_source_numbers(self):
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
                    },
                    {
                        "documentId": "document-2",
                        "title": "제안서.txt",
                        "content": "납기는 별도 협의입니다.",
                    },
                ],
                "history": [],
            }
        )

        user_message = build_chat_prompt(request).messages[-1].content

        self.assertIn("[1] 문서명: 견적서.txt", user_message)
        self.assertIn("문서 ID: document-1", user_message)
        self.assertIn("[2] 문서명: 제안서.txt", user_message)
        self.assertIn("문서 ID: document-2", user_message)
        self.assertIn("질문:\n견적서 리스크를 알려줘", user_message)

    def test_preserves_history_order(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "다시 설명해줘",
                "contexts": [],
                "history": [
                    {"role": "USER", "content": "먼저 요약해줘"},
                    {"role": "ASSISTANT", "content": "요약했습니다. [1]"},
                ],
            }
        )

        prompt = build_chat_prompt(request)

        self.assertEqual(prompt.messages[1].role, "user")
        self.assertEqual(prompt.messages[1].content, "먼저 요약해줘")
        self.assertEqual(prompt.messages[2].role, "assistant")
        self.assertEqual(prompt.messages[2].content, "요약했습니다. [1]")
        self.assertEqual(prompt.messages[3].role, "user")
        self.assertEqual(prompt.messages[3].content, "질문:\n다시 설명해줘")

    def test_system_prompt_contains_risk_and_source_policy(self):
        request = parse_chat_answer_request(
            {
                "projectId": "project-1",
                "ownerId": "owner-1",
                "question": "리스크 알려줘",
                "contexts": [],
                "history": [],
            }
        )

        system_message = build_chat_prompt(request).messages[0].content

        self.assertIn("[1]", system_message)
        self.assertIn("검토 후보", system_message)
        self.assertIn("문서 근거", system_message)
