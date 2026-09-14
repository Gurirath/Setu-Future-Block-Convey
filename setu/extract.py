"""Turning a user's reply into a value for a field the compiled rule asked for.

This module is field-agnostic on purpose. It does not know which fields exist --
the rule compiled from the fetched document decides that, and the agent asks for
whatever that rule left unknown. What lives here is language handling only
(scripts, digits, yes/no), never scheme knowledge.
"""
import re
import unicodedata

# Indic digit forms map to ASCII so numbers parse regardless of script.
DIGIT_MAPS = (
    str.maketrans("०१२३४५६७८९", "0123456789"),
    str.maketrans("௦௧௨௩௪௫௬௭௮௯", "0123456789"),
    str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"),
    str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789"),
)

# Script ranges -> ISO 639-1 code. Script identifies writing system, not language;
# for the scripts below the mapping is unambiguous enough to route a reply.
SCRIPT_RANGES = (
    ((0x0900, 0x097F), "hi"),
    ((0x0980, 0x09FF), "bn"),
    ((0x0A80, 0x0AFF), "gu"),
    ((0x0B80, 0x0BFF), "ta"),
    ((0x0C00, 0x0C7F), "te"),
    ((0x0C80, 0x0CFF), "kn"),
    ((0x0D00, 0x0D7F), "ml"),
)

AFFIRMATIVE = {"yes", "y", "yeah", "yep", "correct", "true", "have", "haan", "han",
               "हां", "आम", "ஆம்", "இருக்கிறது"}
NEGATIVE = {"no", "n", "nope", "not", "false", "none", "nahi", "nahin",
            "नहीं", "इल्लै", "இல்லை"}

# Scale words attach to a bare number ("2 lakh"). Language vocabulary, not scheme data.
SCALES = {
    "lakh": 100_000, "lakhs": 100_000, "lac": 100_000,
    "लाख": 100_000, "லட்சம்": 100_000,
    "crore": 10_000_000, "करोड़": 10_000_000,
    "thousand": 1_000, "हजार": 1_000, "ஆயிரம்": 1_000,
}

# The trailing group must allow combining marks: Python's \w excludes category Mn,
# which would truncate a word like "लाख" to "ल" and silently lose the scale.
NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([^\s\d,.]+)?", re.UNICODE)

# Phrases that express uncertainty outright. Checked before word-level polarity so
# "I'm not sure" reads as unknown rather than as a denial.
UNCERTAIN_PHRASES = ("not sure", "notsure", "dont know", "don't know", "do not know",
                     "no idea", "not certain", "unsure", "maybe", "perhaps",
                     "पता नहीं", "தெரியவில்லை")


def normalize_digits(text: str) -> str:
    for table in DIGIT_MAPS:
        text = text.translate(table)
    return text


def detect_script(text: str) -> str:
    """Return an ISO code for the dominant non-Latin script, else 'en'."""
    counts: dict[str, int] = {}
    for char in text:
        if not char.isalpha():
            continue
        code = ord(char)
        for (low, high), lang in SCRIPT_RANGES:
            if low <= code <= high:
                counts[lang] = counts.get(lang, 0) + 1
                break
    if not counts:
        return "en"
    return max(counts, key=counts.get)


def parse_number(text: str) -> float | None:
    """Extract the first number, applying any scale word that follows it."""
    match = NUMBER.search(normalize_digits(text))
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    suffix = (match.group(2) or "").lower()
    return value * SCALES.get(suffix, 1)


def parse_boolean(text: str) -> bool | None:
    lowered = unicodedata.normalize("NFC", text).lower()
    if any(phrase in lowered for phrase in UNCERTAIN_PHRASES):
        return None
    words = {unicodedata.normalize("NFC", w).strip(".,!?").lower()
             for w in text.split()}
    affirmative = bool(words & AFFIRMATIVE)
    negative = bool(words & NEGATIVE)
    if affirmative == negative:       # both or neither -> ambiguous, stay unknown
        return None
    return affirmative


def parse_value(text: str, expected):
    """Parse a reply into the type the rule's comparison implies. None means unknown."""
    if expected is bool:
        return parse_boolean(text)
    if expected in (int, float):
        number = parse_number(text)
        if number is None:
            return None
        return int(number) if expected is int else number
    stripped = text.strip()
    return stripped or None


def expected_type(rule_value):
    """Infer what a reply should parse to from the value the rule compares against."""
    if isinstance(rule_value, bool):
        return bool
    if isinstance(rule_value, int):
        return int
    if isinstance(rule_value, float):
        return float
    return str
