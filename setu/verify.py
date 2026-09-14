"""Mechanical verification.

A claim ships only if the text it cites is LITERALLY present at its anchor in a
document whose bytes still hash to its fetch record. No model judges this.
"""
import hashlib
from dataclasses import dataclass

from setu.anchor import tokens


@dataclass
class VerificationResult:
    ok: bool
    reason: str
    quote: str = ""


def verify_anchor(anchor: dict, doc) -> VerificationResult:
    if anchor.get("doc_sha256") != doc.sha256:
        return VerificationResult(False, "anchor points at a different document than the one supplied")
    if hashlib.sha256(doc.raw).hexdigest() != doc.sha256:
        return VerificationResult(False, "stored bytes no longer match the fetch record")
    if anchor["end"] > len(doc.text):
        return VerificationResult(False, "anchor range runs past the end of the document")
    quote = doc.slice(anchor["start"], anchor["end"])
    if not quote.strip():
        return VerificationResult(False, "anchor resolves to empty text")
    return VerificationResult(True, "anchor resolves to real text in the fetched document", quote)


def verify_claim(claim_text: str, anchor: dict, doc, min_coverage: float = 0.6) -> VerificationResult:
    """Every content word in the claim must be traceable to the anchored span."""
    anchored = verify_anchor(anchor, doc)
    if not anchored.ok:
        return anchored
    claim_tokens = tokens(claim_text)
    if not claim_tokens:
        return VerificationResult(False, "claim has no content words to verify")
    source_tokens = tokens(anchored.quote)
    covered = claim_tokens & source_tokens
    coverage = len(covered) / len(claim_tokens)
    if coverage < min_coverage:
        unsupported = sorted(claim_tokens - source_tokens)[:6]
        return VerificationResult(
            False,
            f"claim is only {coverage:.0%} grounded in its source; "
            f"unsupported terms: {', '.join(unsupported)}",
            anchored.quote,
        )
    return VerificationResult(True, f"claim is {coverage:.0%} grounded in its source", anchored.quote)
