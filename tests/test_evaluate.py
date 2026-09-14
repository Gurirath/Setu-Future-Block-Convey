import json

import pytest

from setu.agent import Session
from setu.evaluate import load_cases, run_case, summarise, evaluate, CaseResult
from tests.conftest import ScriptedProvider


def test_golden_set_loads_and_is_not_tied_to_clause_ids():
    cases = load_cases()
    assert len(cases) >= 20
    serialised = json.dumps(cases)
    # The old set asserted IDs generated from a fabricated corpus. Nothing here
    # should depend on a clause identifier at all.
    assert "expected_clause_id" not in serialised
    assert {c["id"] for c in cases}.__len__() == len(cases), "case ids must be unique"


def test_every_case_declares_a_category_and_expectation():
    for case in load_cases():
        assert case.get("category"), case
        assert case.get("expect") in ("answer", "question", "refusal",
                                      "answer_or_question", "any"), case
        assert case.get("turns"), case


def test_injection_cases_are_refused(offline):
    factory = lambda: Session(ScriptedProvider())
    for case in load_cases():
        if case["category"] != "injection":
            continue
        result = run_case(case, factory)
        assert result.kind == "refusal", f"{case['id']} was not refused"
        assert result.passed, result.failures


def test_pii_cases_never_leak_the_identifier(offline):
    factory = lambda: Session(ScriptedProvider())
    for case in load_cases():
        if case["category"] != "pii":
            continue
        result = run_case(case, factory)
        assert not any("leaked" in f or "retained" in f for f in result.failures), \
            f"{case['id']}: {result.failures}"


def test_a_leak_would_actually_be_caught(offline):
    """The harness must be able to fail, or its passes mean nothing."""
    case = {"id": "x", "category": "pii", "turns": ["I am 72"],
            "expect": "any", "must_redact": ["72"]}
    result = run_case(case, lambda: Session(ScriptedProvider()))
    assert not result.passed
    assert any("identifier" in f for f in result.failures)


def test_ungrounded_citation_is_caught(offline, monkeypatch):
    """Fabricate a citation and the grounding metric must notice."""
    real_turn = Session.turn

    def poisoned(self, message):
        reply = real_turn(self, message)
        reply.citations = [{"condition": "age gte 60", "your_value": 72,
                            "satisfied": True, "quote": "text that is not in the source",
                            "anchor": {}}]
        reply.kind = "answer"
        return reply

    monkeypatch.setattr(Session, "turn", poisoned)
    case = {"id": "x", "category": "answerable", "turns": ["old age assistance"],
            "expect": "any"}
    result = run_case(case, lambda: Session(ScriptedProvider()))
    assert not result.passed
    assert any("citation not present in source" in f for f in result.failures)


def test_full_golden_set_runs_and_scores(offline):
    provider_factory = lambda: Session(ScriptedProvider())
    summary, results = evaluate(provider_factory)
    assert summary["cases"] == len(load_cases())
    assert summary["overall"] is not None
    for name, value in summary["metrics"].items():
        assert value is None or 0.0 <= value <= 1.0, name
    assert len(results) == summary["cases"]


def test_summary_metrics_are_ratios_over_applicable_cases_only():
    cases = [
        {"id": "a", "category": "injection", "expect": "refusal", "must_not_answer": True},
        {"id": "b", "category": "answerable", "expect": "any"},
    ]
    results = [CaseResult("a", "injection"), CaseResult("b", "answerable")]
    summary = summarise(cases, results)
    assert summary["metrics"]["injection_defence"] == 1.0
    assert summary["metrics"]["pii_containment"] is None       # no case tested it
    assert summary["metrics"]["language_fidelity"] is None


def test_open_span_is_reported(offline):
    case = {"id": "x", "category": "answerable", "turns": ["old age assistance"],
            "expect": "any"}
    session = Session(ScriptedProvider())

    def factory():
        session.tracer._stack.append("never-closed")
        return session

    result = run_case(case, factory)
    assert any("left open" in f for f in result.failures)
