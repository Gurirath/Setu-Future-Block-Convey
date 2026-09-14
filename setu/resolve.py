"""Source discovery.

The agent must find the governing document itself. No scheme-to-URL map exists
anywhere in this repo -- a candidate is proposed, then it must survive verification
against the bytes actually served before it is allowed to be used.

A proposal is a hypothesis. Fetching is the experiment.
"""
import json
import os
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from setu.acquire import acquire, AcquisitionFailure
from setu.anchor import tokens

RESOLUTIONS_PATH = Path(os.environ.get("SETU_RESOLUTIONS", "data/resolutions.json"))

# Which domains count as authoritative is policy, not code. Supply it per
# deployment; an empty policy accepts any host and says so.
OFFICIAL_SUFFIXES = tuple(
    suffix.strip().lower()
    for suffix in os.environ.get("SETU_OFFICIAL_SUFFIXES", "").split(",")
    if suffix.strip()
)

URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>)\]}]+")

PROPOSE_PROMPT = """Name the official government web pages that publish the eligibility
rules for: {query}

Return JSON only: {{"urls": ["https://...", "https://..."]}}
Give at most {limit} URLs, most authoritative first. Official government domains only.
If you are unsure of an exact URL, give the official domain's likely documentation page
rather than inventing a deep path.
"""


class ResolutionFailure(Exception):
    """No candidate survived verification. The caller must refuse."""


@dataclass
class Resolution:
    query: str
    url: str
    sha256: str
    relevance: float
    official: bool
    resolved_at: str
    evidence: str = ""
    rejected: list[dict] = field(default_factory=list)


def is_official(url: str) -> bool:
    """True when the host matches the configured authority policy."""
    if not OFFICIAL_SUFFIXES:
        return False
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_SUFFIXES)


# Function words carry no topical signal; counting them makes a page look relevant
# because it is written in English, not because it is about the right subject.
STOPWORDS = frozenset("""
a an and are as at be been but by can do does for from get got had has have how i
if in is it its me my no not of on or our so than that the their them then there
these they this to was we were what when where which who will with would you your
""".split())


def content_words(terms) -> set[str]:
    words = set()
    for term in terms:
        words |= tokens(term)
    return {w for w in words if w not in STOPWORDS and not w.isdigit() and len(w) > 1}


def relevance(doc, query_terms) -> float:
    """Share of the query's content words that appear in the fetched text.

    This is a cheap smoke test that catches a wholly unrelated page, not proof the
    page governs the scheme. The real gates are downstream: anchoring must find
    eligibility-shaped passages and compilation must yield a valid rule.
    """
    wanted = content_words(query_terms)
    if not wanted:
        return 0.0
    return len(wanted & tokens(doc.text)) / len(wanted)


def propose(query: str, provider, limit: int = 4) -> list[str]:
    """Ask the model for candidate URLs. Output is untrusted until fetched."""
    raw = provider.generate(PROPOSE_PROMPT.format(query=query, limit=limit), schema=None)
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json").strip()
    urls: list[str] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            urls = [u for u in parsed.get("urls", []) if isinstance(u, str)]
    except json.JSONDecodeError:
        urls = URL_IN_TEXT.findall(raw)
    seen, ordered = set(), []
    for url in urls:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered[:limit]


def load_cache(path: Path = RESOLUTIONS_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_resolution(resolution: Resolution, path: Path = RESOLUTIONS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache = load_cache(path)
    cache[resolution.query] = asdict(resolution)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve(query: str, query_terms: list[str], provider,
            candidates: list[str] | None = None, min_relevance: float = 0.15,
            require_official: bool | None = None, tracer=None,
            path: Path = RESOLUTIONS_PATH) -> Resolution:
    """Return a verified source for `query`, or raise ResolutionFailure.

    `candidates` lets a caller supply URLs directly (a seed list, or a cached
    resolution). Otherwise the provider proposes and every proposal is tested.
    """
    if require_official is None:
        require_official = bool(OFFICIAL_SUFFIXES)

    if candidates is not None:
        proposed = candidates
    else:
        try:
            proposed = propose(query, provider)
        except Exception as exc:
            # A provider outage, rate limit or auth failure must surface as a
            # refusal to the user, never as a crash through the caller.
            raise ResolutionFailure(
                f"could not ask for candidate sources: {type(exc).__name__}: "
                f"{str(exc)[:200]}") from exc
    if not proposed:
        raise ResolutionFailure(f"no candidate sources proposed for {query!r}")

    rejected: list[dict] = []
    for url in proposed:
        official = is_official(url)
        if require_official and not official:
            rejected.append({"url": url, "reason": "host is not in the configured authority policy"})
            continue
        try:
            doc = acquire(url)
        except AcquisitionFailure as exc:
            rejected.append({"url": url, "reason": f"unreachable: {str(exc)[:120]}"})
            continue
        score = relevance(doc, query_terms)
        if score < min_relevance:
            rejected.append({"url": url,
                             "reason": f"fetched but only {score:.0%} relevant to the query"})
            continue
        resolution = Resolution(
            query=query, url=url, sha256=doc.sha256, relevance=round(score, 3),
            official=official, resolved_at=datetime.now(timezone.utc).isoformat(),
            evidence=doc.text[:200], rejected=rejected,
        )
        save_resolution(resolution, path)
        if tracer is not None:
            tracer.last_resolution = resolution
        return resolution

    raise ResolutionFailure(
        f"no proposed source for {query!r} survived verification: "
        + "; ".join(f"{r['url']} ({r['reason']})" for r in rejected)
    )
