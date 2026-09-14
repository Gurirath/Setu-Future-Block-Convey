import pytest

from setu.resolve import (resolve, propose, relevance, is_official,
                          ResolutionFailure, Resolution)
from setu.acquire import AcquisitionFailure
from tests.conftest import ScriptedProvider

TERMS = ["eligibility", "applicant", "pension"]


def test_proposed_url_must_survive_fetching(offline, provider):
    resolution = resolve("old age assistance", TERMS, provider)
    assert isinstance(resolution, Resolution)
    assert resolution.url == "https://source.test/scheme"
    assert resolution.relevance >= 0.3
    assert resolution.sha256 == offline.sha256


def test_unreachable_candidate_is_rejected_and_next_one_tried(monkeypatch, document,
                                                              provider):
    monkeypatch.setattr("setu.resolve.save_resolution", lambda r, path=None: None)
    monkeypatch.setattr("setu.resolve.OFFICIAL_SUFFIXES", ())
    provider.urls = ["https://dead.test/", "https://source.test/scheme"]

    def fetch(url, **kwargs):
        if "dead" in url:
            raise AcquisitionFailure(url, [{"rung": "http_static", "outcome": "DNS failure"}])
        return document

    monkeypatch.setattr("setu.resolve.acquire", fetch)
    resolution = resolve("old age assistance", TERMS, provider)
    assert resolution.url == "https://source.test/scheme"
    assert resolution.rejected[0]["url"] == "https://dead.test/"
    assert "unreachable" in resolution.rejected[0]["reason"]


def test_irrelevant_page_is_rejected(offline, provider):
    with pytest.raises(ResolutionFailure, match="relevant"):
        resolve("tractor subsidy", ["tractor", "subsidy", "machinery"], provider,
                min_relevance=0.9)


def test_no_proposals_refuses(offline):
    with pytest.raises(ResolutionFailure, match="no candidate sources proposed"):
        resolve("anything", TERMS, ScriptedProvider(urls=[]))


def test_all_candidates_failing_refuses_with_reasons(monkeypatch, provider):
    monkeypatch.setattr("setu.resolve.OFFICIAL_SUFFIXES", ())

    def fetch(url, **kwargs):
        raise AcquisitionFailure(url, [{"rung": "http_static", "outcome": "timeout"}])

    monkeypatch.setattr("setu.resolve.acquire", fetch)
    with pytest.raises(ResolutionFailure, match="survived verification"):
        resolve("old age assistance", TERMS, provider)


def test_authority_policy_rejects_unofficial_hosts(monkeypatch, document, provider):
    monkeypatch.setattr("setu.resolve.OFFICIAL_SUFFIXES", ("gov.example",))
    monkeypatch.setattr("setu.resolve.acquire", lambda url, **kw: document)
    monkeypatch.setattr("setu.resolve.save_resolution", lambda r, path=None: None)
    with pytest.raises(ResolutionFailure, match="authority policy"):
        resolve("old age assistance", TERMS, provider, require_official=True)


def test_authority_policy_accepts_matching_host(monkeypatch, document):
    monkeypatch.setattr("setu.resolve.OFFICIAL_SUFFIXES", ("gov.example",))
    monkeypatch.setattr("setu.resolve.acquire", lambda url, **kw: document)
    monkeypatch.setattr("setu.resolve.save_resolution", lambda r, path=None: None)
    provider = ScriptedProvider(urls=["https://welfare.gov.example/scheme"])
    resolution = resolve("old age assistance", TERMS, provider, require_official=True)
    assert resolution.official is True


def test_is_official_matches_host_and_subdomains(monkeypatch):
    monkeypatch.setattr("setu.resolve.OFFICIAL_SUFFIXES", ("gov.example",))
    assert is_official("https://gov.example/x")
    assert is_official("https://dept.gov.example/x")
    assert not is_official("https://gov.example.attacker.test/x")
    assert not is_official("https://notgov.example2/x")


def test_empty_policy_marks_nothing_official(monkeypatch):
    monkeypatch.setattr("setu.resolve.OFFICIAL_SUFFIXES", ())
    assert is_official("https://anything.test/") is False


def test_propose_recovers_urls_from_unfenced_prose():
    provider = ScriptedProvider()
    provider.generate = lambda prompt, schema=None: (
        "I think https://a.test/one and https://b.test/two are right.")
    assert propose("q", provider) == ["https://a.test/one", "https://b.test/two"]


def test_propose_deduplicates_and_limits():
    provider = ScriptedProvider(urls=["https://a.test/", "https://a.test/",
                                      "https://b.test/", "https://c.test/"])
    assert propose("q", provider, limit=2) == ["https://a.test/", "https://b.test/"]


def test_relevance_is_share_of_query_terms_present(document):
    assert relevance(document, ["applicant", "pension"]) == 1.0
    assert relevance(document, ["tractor", "helicopter"]) == 0.0
    assert relevance(document, []) == 0.0


def test_provider_failure_becomes_a_refusal_not_a_crash(monkeypatch):
    """A rate limit during proposal must not escape as an exception."""
    monkeypatch.setattr("setu.resolve.OFFICIAL_SUFFIXES", ())

    class Exhausted:
        def generate(self, prompt, schema=None):
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")

    with pytest.raises(ResolutionFailure, match="could not ask for candidate sources"):
        resolve("anything", TERMS, Exhausted())
