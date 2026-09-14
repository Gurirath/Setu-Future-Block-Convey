"""End-to-end tests for the orchestrator.

The document here is synthetic ON PURPOSE: these tests exercise the plumbing
(acquire -> anchor -> compile -> adjudicate -> verify), not any real scheme's
semantics. Real-source behaviour is exercised by scripts/live_check.py.
"""
import json

import pytest

from setu.pipeline import answer
from setu.provenance import make_document

BODY = (
    "Eligibility conditions for the assistance programme\n"
    "The applicant must be sixty years of age or older to qualify for assistance.\n"
    "Applicants who already draw a pension from another programme are excluded.\n"
    "Payment is made in three instalments directly to the beneficiary account.\n"
    + ("Additional procedural notes follow in this section. " * 30)
)


class StubProvider:
    """Stands in for the model. Returns a fixed predicate citing span indices."""

    def __init__(self, payload):
        self.payload = payload

    def generate(self, prompt, schema=None):
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


@pytest.fixture
def local_source(monkeypatch):
    """Serve a fixed document through the real acquisition path."""
    raw = BODY.encode("utf-8")
    doc = make_document(raw, BODY, "https://example.test/scheme", 200,
                        "text/html", "http_static+html")
    monkeypatch.setattr("setu.pipeline.acquire", lambda url, **kw: doc)
    monkeypatch.setattr("setu.pipeline.provenance.save", lambda d: None)
    return doc


RULE = {"op": "and", "args": [
    {"op": "gte", "field": "age", "value": 60, "span": 0},
    {"op": "not", "args": [{"op": "eq", "field": "has_other_pension", "value": True, "span": 1}]},
]}
TERMS = ["eligibility", "applicant", "age", "pension"]


def test_eligible_answer_carries_verified_citations(local_source):
    result = answer("https://example.test/scheme",
                    {"age": 72, "has_other_pension": False}, TERMS,
                    provider=StubProvider(RULE))
    assert result.outcome == "eligible"
    assert result.citations, "an eligible answer must carry citations"
    for citation in result.citations:
        assert citation["quote"].strip(), "every citation must quote real source text"
        assert citation["quote"] in local_source.text
    assert result.fetched_at and result.trace_id


def test_not_eligible_is_also_cited(local_source):
    result = answer("https://example.test/scheme",
                    {"age": 40, "has_other_pension": False}, TERMS,
                    provider=StubProvider(RULE))
    assert result.outcome == "not_eligible"
    assert any(c["satisfied"] is False for c in result.citations)


def test_missing_data_asks_instead_of_deciding(local_source):
    result = answer("https://example.test/scheme", {"age": 72}, TERMS,
                    provider=StubProvider(RULE))
    assert result.outcome == "need_more_info"
    assert result.ask_for == "has_other_pension"


def test_question_is_derived_not_hardcoded(local_source):
    """Change the compiled rule and the question the agent asks changes with it."""
    other = {"op": "gte", "field": "land_size_acres", "value": 2, "span": 0}
    result = answer("https://example.test/scheme", {}, TERMS, provider=StubProvider(other))
    assert result.ask_for == "land_size_acres"


def test_authority_gated_scheme_refuses(local_source):
    rule = {"op": "requires_authority",
            "authority": "the official beneficiary register", "span": 0}
    result = answer("https://example.test/scheme", {"age": 72}, TERMS,
                    provider=StubProvider(rule))
    assert result.outcome == "refused"
    assert "register" in result.refusal_reason


def test_model_inventing_a_span_causes_refusal(local_source):
    bad = {"op": "gte", "field": "age", "value": 60, "span": 999}
    result = answer("https://example.test/scheme", {"age": 72}, TERMS,
                    provider=StubProvider(bad))
    assert result.outcome == "refused"
    assert "were offered" in result.refusal_reason


def test_model_prose_instead_of_json_causes_refusal(local_source):
    result = answer("https://example.test/scheme", {"age": 72}, TERMS,
                    provider=StubProvider("You are definitely eligible!"))
    assert result.outcome == "refused"
    assert "valid JSON" in result.refusal_reason


def test_unreachable_source_refuses_and_never_invents(monkeypatch):
    from setu.acquire import AcquisitionFailure

    def boom(url, **kwargs):
        raise AcquisitionFailure(url, [{"rung": "http_static", "outcome": "DNS failure"}])

    monkeypatch.setattr("setu.pipeline.acquire", boom)
    result = answer("https://unreachable.test/", {"age": 72}, TERMS,
                    provider=StubProvider(RULE))
    assert result.outcome == "refused"
    assert result.citations == []
    assert "DNS failure" in result.refusal_reason
