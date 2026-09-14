import json

import pytest

from setu.anchor import Span
from setu.compile_rule import compile_rule, CompilationError
from setu.rules import validate

SPANS = [
    Span("abc123", 0, 30, "The applicant must be 60 years or older."),
    Span("abc123", 31, 70, "Applicants already drawing a pension are excluded."),
]


class FakeProvider:
    """Stands in for a model so compilation logic is testable without any key."""

    name = "fake"
    model = "fake"

    def __init__(self, payload):
        self.payload = payload
        self.last_schema = None

    def generate(self, prompt, schema=None):
        self.last_schema = schema
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


def test_span_index_becomes_a_real_anchor():
    rule = compile_rule(SPANS, FakeProvider(
        {"op": "and", "args": [
            {"op": "gte", "field": "age", "value": 60, "span": 0},
            {"op": "not", "args": [
                {"op": "eq", "field": "has_pension", "value": True, "span": 1}]},
        ]}))
    validate(rule)
    assert rule["args"][0]["anchor"] == {"doc_sha256": "abc123", "start": 0, "end": 30}
    assert "span" not in rule["args"][0]


def test_invented_span_index_is_rejected():
    with pytest.raises(CompilationError, match="only 0..1 were offered"):
        compile_rule(SPANS, FakeProvider({"op": "gte", "field": "age", "value": 60, "span": 7}))


def test_boolean_is_not_accepted_as_a_span_index():
    with pytest.raises(CompilationError, match="were offered"):
        compile_rule(SPANS, FakeProvider(
            {"op": "gte", "field": "age", "value": 60, "span": True}))


def test_leaf_without_a_span_is_rejected():
    with pytest.raises(CompilationError, match="cites no span"):
        compile_rule(SPANS, FakeProvider({"op": "gte", "field": "age", "value": 60}))


def test_non_json_is_rejected():
    with pytest.raises(CompilationError, match="valid JSON"):
        compile_rule(SPANS, FakeProvider("Sure! Here is the rule you asked for."))


def test_empty_response_is_rejected():
    with pytest.raises(CompilationError, match="valid JSON"):
        compile_rule(SPANS, FakeProvider(""))


def test_markdown_fence_is_tolerated():
    rule = compile_rule(SPANS, FakeProvider(
        '```json\n{"op":"gte","field":"age","value":60,"span":0}\n```'))
    assert rule["anchor"]["start"] == 0


def test_provider_exception_becomes_refusal_not_crash():
    with pytest.raises(CompilationError, match="model call failed"):
        compile_rule(SPANS, FakeProvider(RuntimeError("upstream 503")))


def test_grammar_schema_is_offered_to_the_provider():
    provider = FakeProvider({"op": "gte", "field": "age", "value": 60, "span": 0})
    compile_rule(SPANS, provider)
    assert provider.last_schema is not None
    assert provider.last_schema["properties"]["op"]["type"] == "string"


def test_no_provider_configured_refuses_instead_of_guessing(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "SETU_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(CompilationError, match="Refusing rather than falling back"):
        compile_rule(SPANS)


def test_no_spans_refuses():
    with pytest.raises(CompilationError, match="nothing can be compiled"):
        compile_rule([], FakeProvider({}))
