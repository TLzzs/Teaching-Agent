import json

import pytest
from fastapi.testclient import TestClient

from app.llm.mock import MockProvider
from app.llm.provider import CompletionRequest
from app.main import create_app


class ScriptedProvider(MockProvider):
    """Mock provider whose replies can be overridden per call, for testing retries and fixes."""

    name = "scripted"

    def __init__(self, section_replies=None, fix_replies=None):
        self.section_replies = section_replies or {}
        self.fix_replies = list(fix_replies or [])
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> str:
        self.requests.append(request)
        if request.meta.get("kind") == "fix" and self.fix_replies:
            return self.fix_replies.pop(0)
        section = request.meta.get("section")
        if section is not None and self.section_replies.get(section.id):
            return self.section_replies[section.id].pop(0)
        return await super().complete(request)


def question_json(prompt: str, answer: str, expression: str, expected: str, **extra) -> dict:
    return {
        "prompt": prompt,
        "answer": answer,
        "working": "",
        "check": {"expression": expression, "expected": expected},
        **extra,
    }


def question_set(*questions: dict) -> str:
    return json.dumps({"questions": list(questions)})


@pytest.fixture
def client():
    return TestClient(create_app(MockProvider()))
