"""Input guardrails.

Users describing their circumstances often volunteer identifiers they should not.
Nothing here encodes scheme knowledge; these are document-number and contact
shapes, plus a check that retrieved source text is treated as data, not instructions.
"""
import re
from dataclasses import dataclass, field

# Identifier shapes, not values. Ordered MOST SPECIFIC FIRST: the broad digit-run
# pattern must run last, or it swallows phone and Aadhaar-shaped numbers.
# Twelve-digit runs are labelled aadhaar_like rather than aadhaar -- the shape is
# suggestive, not proof, and the label should not overclaim.
PATTERNS = (
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("aadhaar_like", re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")),
    ("phone", re.compile(r"\b(?:\+\d{1,3}[\s-]?)?[6-9]\d{9}\b")),
    ("account", re.compile(r"\b\d{9,18}\b")),
)

# Phrasing that tries to make retrieved text act as instructions rather than evidence.
INJECTION = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"
    r"|disregard\s+(?:the\s+)?(?:above|previous)"
    r"|you\s+are\s+now\s+(?:a|an)\s"
    r"|system\s*prompt"
    r"|reveal\s+your\s+(?:prompt|instructions)",
    re.IGNORECASE,
)


@dataclass
class Screening:
    text: str
    redactions: list[str] = field(default_factory=list)
    injection_detected: bool = False

    @property
    def clean(self) -> bool:
        return not self.redactions and not self.injection_detected


def redact(text: str) -> Screening:
    """Replace identifier-shaped tokens with typed placeholders."""
    result = text
    found: list[str] = []
    for label, pattern in PATTERNS:
        def replace(match, label=label):
            found.append(label)
            return f"[{label} redacted]"
        result = pattern.sub(replace, result)
    return Screening(text=result, redactions=found,
                     injection_detected=bool(INJECTION.search(text)))


def screen_source(text: str) -> bool:
    """True when retrieved source text carries instruction-shaped content.

    Source documents are evidence. If a fetched page contains text shaped like an
    instruction, the caller should decline to compile a rule from it.
    """
    return bool(INJECTION.search(text))
