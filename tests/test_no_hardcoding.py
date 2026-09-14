"""Executable proof of the core claim: no scheme knowledge lives in source code.

If anyone adds a scheme name, a government URL, a currency amount, or an
eligibility threshold to setu/, this test fails. The claim is enforced, not asserted.
"""
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "setu"
SOURCES = sorted(PACKAGE.glob("*.py"))

SCHEME_TOKENS = ["pmkisan", "pm-kisan", "pmjay", "pm-jay", "ayushman", "nsap",
                 "ignoaps", "pmayg", "awaas", "tnoap", "cmchis", "samman nidhi",
                 "jan arogya", "secc"]
STATE_TOKENS = ["tamil nadu", "tamilnadu", "karnataka", "maharashtra", "kerala",
                "odisha", "bihar", "uttar pradesh", "meghalaya"]

GOV_DOMAIN = re.compile(r"[\w.-]+\.(?:gov|nic)\.in", re.I)
# \b and a required digit: without them, "rs\.?[\d,]+" matches the "rs," inside
# ordinary words like "answers, asks" and the guard cries wolf.
RUPEE_AMOUNT = re.compile(r"\b(?:rs\.?|rupees?)\s*\d[\d,]*", re.I)
THRESHOLD = re.compile(r"\b(?:age|income|acres?|land)\b\s*[<>=]{1,2}\s*\d+", re.I)
FAKE_HELPLINE = re.compile(r"1800[\s-]?[x\d]{3}[\s-]?[x\d]{4}", re.I)


def _scan_tokens(tokens):
    hits = []
    for path in SOURCES:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            low = line.lower()
            for token in tokens:
                if token in low:
                    hits.append(f"{path.name}:{lineno}: {line.strip()}")
    return hits


def _scan_regex(pattern):
    hits = []
    for path in SOURCES:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{path.name}:{lineno}: {line.strip()}")
    return hits


def test_package_is_not_empty():
    assert SOURCES, "no source files found to scan"


def test_no_scheme_names_in_source():
    hits = _scan_tokens(SCHEME_TOKENS)
    assert not hits, "scheme names found in source:\n" + "\n".join(hits)


def test_no_state_names_in_source():
    hits = _scan_tokens(STATE_TOKENS)
    assert not hits, "state names found in source:\n" + "\n".join(hits)


def test_no_government_urls_in_source():
    hits = _scan_regex(GOV_DOMAIN)
    assert not hits, "government URLs found in source:\n" + "\n".join(hits)


def test_no_currency_amounts_in_source():
    hits = _scan_regex(RUPEE_AMOUNT)
    assert not hits, "currency amounts found in source:\n" + "\n".join(hits)


def test_no_eligibility_thresholds_in_source():
    hits = _scan_regex(THRESHOLD)
    assert not hits, "eligibility thresholds found in source:\n" + "\n".join(hits)


def test_no_placeholder_helpline_numbers():
    hits = _scan_regex(FAKE_HELPLINE)
    assert not hits, "placeholder helpline found in source:\n" + "\n".join(hits)


def test_guard_actually_catches_a_violation(tmp_path, monkeypatch):
    """The guard must be capable of failing -- otherwise it proves nothing."""
    offender = tmp_path / "bad.py"
    offender.write_text(
        "AGE_LIMIT = 60  # age >= 60\n"
        "URL = 'https://pmkisan.gov.in/'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("tests.test_no_hardcoding.SOURCES", [offender])
    assert _scan_tokens(SCHEME_TOKENS)
    assert _scan_regex(GOV_DOMAIN)
    assert _scan_regex(THRESHOLD)
