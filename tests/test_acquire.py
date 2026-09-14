import pytest

from setu.acquire import acquire, AcquisitionFailure, RUNGS
from setu.provenance import make_document


def doc(text="x" * 2000, url="https://s.test/"):
    return make_document(text.encode(), text, url, 200, "text/html", "stub")


def test_first_sufficient_rung_wins():
    rungs = (("a", lambda u: doc()), ("b", lambda u: pytest.fail("should not reach")))
    assert acquire("https://s.test/", rungs=rungs).text.startswith("x")


def test_failing_rung_escalates_to_the_next():
    def boom(url):
        raise RuntimeError("blocked")
    result = acquire("https://s.test/", rungs=(("a", boom), ("b", lambda u: doc())))
    assert result.text.startswith("x")


def test_insufficient_content_escalates():
    calls = []

    def thin(url):
        calls.append("thin")
        return doc("tiny")

    def full(url):
        calls.append("full")
        return doc()

    acquire("https://s.test/", sufficient=lambda d: len(d.text) > 100,
            rungs=(("a", thin), ("b", full)))
    assert calls == ["thin", "full"]


def test_all_rungs_failing_raises_with_every_reason():
    def boom(url):
        raise RuntimeError("blocked")
    with pytest.raises(AcquisitionFailure) as exc:
        acquire("https://s.test/", rungs=(("a", boom), ("b", boom)))
    assert len(exc.value.attempts) == 2
    assert "blocked" in str(exc.value)


def test_never_returns_a_document_when_everything_fails():
    def boom(url):
        raise RuntimeError("blocked")
    with pytest.raises(AcquisitionFailure):
        acquire("https://s.test/", rungs=(("a", boom),))


def test_ladder_order_is_cheapest_first():
    assert [name for name, _ in RUNGS] == ["http_static", "headless", "linked_pdf"]
