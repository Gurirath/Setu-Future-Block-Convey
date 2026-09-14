import json

import pytest

from setu.provenance import make_document

BODY = (
    "Eligibility conditions for the assistance programme\n"
    "The applicant must be sixty years of age or older to qualify for assistance.\n"
    "Applicants who already draw a pension from another programme are excluded.\n"
    "Payment is made in three instalments directly to the beneficiary account.\n"
    + ("Additional procedural notes follow in this section. " * 30)
)

RULE_PAYLOAD = {"op": "and", "args": [
    {"op": "gte", "field": "age", "value": 60, "span": 0},
    {"op": "not", "args": [
        {"op": "eq", "field": "has_other_pension", "value": True, "span": 1}]},
]}


class ScriptedProvider:
    """Routes by prompt shape so one stub can serve every model call in a turn.

    Each hook may be a value or a callable. Calls are recorded for assertions.
    """

    name = "scripted"
    model = "scripted"

    def __init__(self, *, rule=None, urls=None, facts=None, question=None,
                 translation=None, search_keywords="eligibility applicant pension age"):
        self.rule = RULE_PAYLOAD if rule is None else rule
        self.urls = ["https://source.test/scheme"] if urls is None else urls
        self.facts = facts or {}
        self.question = question
        self.translation = translation
        self.search_keywords = search_keywords
        self.calls: list[str] = []

    def _kind(self, prompt: str) -> str:
        if "Name the official government web pages" in prompt:
            return "propose"
        if "Convert ONLY the eligibility conditions" in prompt:
            return "compile"
        if "extract any of these facts" in prompt:
            return "extract"
        if "Write one short, plain question" in prompt:
            return "ask"
        if "Rewrite this message" in prompt:
            return "translate"
        if "English search keywords" in prompt:
            return "search"
        return "unknown"

    def generate(self, prompt, schema=None):
        kind = self._kind(prompt)
        self.calls.append(kind)
        if kind == "propose":
            return json.dumps({"urls": self.urls})
        if kind == "compile":
            if isinstance(self.rule, Exception):
                raise self.rule
            return self.rule if isinstance(self.rule, str) else json.dumps(self.rule)
        if kind == "extract":
            return json.dumps(self.facts() if callable(self.facts) else self.facts)
        if kind == "ask":
            return self.question or "What is your age?"
        if kind == "translate":
            return self.translation or "translated message"
        if kind == "search":
            return self.search_keywords
        return "{}"


@pytest.fixture
def document():
    return make_document(BODY.encode("utf-8"), BODY, "https://source.test/scheme",
                         200, "text/html", "http_static+html")


@pytest.fixture
def offline(monkeypatch, document):
    """Serve `document` for any fetch, and keep resolution cache off disk."""
    monkeypatch.setattr("setu.agent.acquire", lambda url, **kw: document)
    monkeypatch.setattr("setu.resolve.acquire", lambda url, **kw: document)
    monkeypatch.setattr("setu.agent.provenance.save", lambda d: None)
    monkeypatch.setattr("setu.resolve.save_resolution", lambda r, path=None: None)
    monkeypatch.setattr("setu.resolve.OFFICIAL_SUFFIXES", ())
    return document


@pytest.fixture
def provider():
    return ScriptedProvider()
