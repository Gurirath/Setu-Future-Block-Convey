"""Structural segmentation of a fetched document into anchored spans.

A clause identity is a byte range into the stored document text -- not a label a
model invented. That is what makes "this claim is bound to a clause" checkable.
"""
import re
from dataclasses import dataclass

BLOCK_SPLIT = re.compile(r"\n")
WORD = re.compile(r"[a-z0-9]+")
# A heading-ish line: short, no terminal period, often numbered.
HEADING = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?[^.]{3,80}$")


@dataclass(frozen=True)
class Span:
    doc_sha256: str
    start: int
    end: int
    text: str
    heading: str = ""

    def as_anchor(self) -> dict:
        return {"doc_sha256": self.doc_sha256, "start": self.start, "end": self.end}


def segment(doc, min_chars: int = 40) -> list[Span]:
    """Split document text into spans, tracking exact offsets into doc.text."""
    spans: list[Span] = []
    text = doc.text
    offset = 0
    current_heading = ""
    for line in BLOCK_SPLIT.split(text):
        start, end = offset, offset + len(line)
        offset = end + 1  # account for the '\n' consumed by split
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) < min_chars and HEADING.match(stripped):
            current_heading = stripped
            continue
        lead = len(line) - len(line.lstrip())
        spans.append(Span(doc.sha256, start + lead, end, line.strip(), current_heading))
    return spans


def tokens(s: str) -> set[str]:
    return set(WORD.findall(s.lower()))


def rank(spans: list[Span], query_terms: list[str], top_k: int = 5) -> list[tuple[Span, float]]:
    """Deterministic lexical ranking. Terms come from the caller at runtime."""
    wanted = set()
    for term in query_terms:
        wanted |= tokens(term)
    if not wanted:
        return []
    scored = []
    for span in spans:
        have = tokens(span.text) | tokens(span.heading)
        if not have:
            continue
        overlap = len(wanted & have)
        if overlap:
            scored.append((span, overlap / len(wanted)))
    scored.sort(key=lambda pair: (-pair[1], pair[0].start))
    return scored[:top_k]
