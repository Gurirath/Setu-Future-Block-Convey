import re

from agent.profile import UserProfile, QUESTIONS, missing_slots

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
TAMIL_DIGITS = str.maketrans("௦௧௨௩௪௫௬௭௮௯", "0123456789")

AGE_PATTERN = re.compile(
    r"(\d{1,3})\s*(?:years?\s*old|yrs?\s*old|yrs?|साल|वर्ष|வயது|வயதாக)"
    r"|\bi\s*am\s*(\d{1,3})\b"
    r"|\bage\s*(?:is|:)?\s*(\d{1,3})\b",
    re.IGNORECASE,
)

LAND_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:acres?|एकड़|ஏக்கர்)",
    re.IGNORECASE,
)

INCOME_PATTERN = re.compile(
    r"(?:income|salary|earn|आय|वेतन|வருமானம்)[^\d]{0,20}"
    r"(?:rs\.?|₹|rupees?|रुपये|ரூபாய்)?\s*"
    r"(\d[\d,]*)\s*"
    r"(lakh|lakhs|लाख|லட்சம்|thousand|हज़ार|ஆயிரம்)?"
    r"[^.]{0,10}?"
    r"(month|monthly|महीने|मासिक|மாதம்|year|yearly|annual|साल|वार्षिक|ஆண்டு)?",
    re.IGNORECASE,
)

STATE_ALIASES = {
    "tamil nadu": "Tamil Nadu",
    "tamilnadu": "Tamil Nadu",
    "தமிழ்நாடு": "Tamil Nadu",
    "தமிழ்நாட்டில்": "Tamil Nadu",
    "தமிழ்நாட்டின்": "Tamil Nadu",
    "तमिलनाडु": "Tamil Nadu",
    "तमिलनाडु में": "Tamil Nadu",
    "maharashtra": "Maharashtra",
    "महाराष्ट्र": "Maharashtra",
    "kerala": "Kerala",
    "केरल": "Kerala",
    "karnataka": "Karnataka",
    "odisha": "Odisha",
    "bihar": "Bihar",
    "uttar pradesh": "Uttar Pradesh",
}

BPL_TRUE_PATTERN = re.compile(
    r"bpl\s*card|below\s*poverty\s*line|बीपीएल|பிபிஎல்", re.IGNORECASE
)
BPL_FALSE_PATTERN = re.compile(
    r"no\s*bpl|not\s*bpl|above\s*poverty\s*line|बीपीएल\s*नहीं", re.IGNORECASE
)

DESTITUTE_TRUE_PATTERN = re.compile(
    r"no\s*(?:regular\s*)?income|no\s*support|आय\s*नहीं|सहारा\s*नहीं|வருமானம்\s*இல்லை",
    re.IGNORECASE,
)
DESTITUTE_FALSE_PATTERN = re.compile(
    r"have\s*(?:a\s*)?(?:regular\s*)?income|family\s*supports?\s*me",
    re.IGNORECASE,
)

PUCCA_TRUE_PATTERN = re.compile(
    r"pucca\s*house|concrete\s*house|पक्का\s*मकान|பக்கா\s*வீடு", re.IGNORECASE
)
PUCCA_FALSE_PATTERN = re.compile(
    r"kutcha\s*house|katcha\s*house|houseless|no\s*house|कच्चा\s*मकान|வீடு\s*இல்லை",
    re.IGNORECASE,
)

RATION_MENTION_PATTERN = re.compile(
    r"ration\s*card|राशन\s*कार्ड|ரேஷன்\s*அட்டை", re.IGNORECASE
)
RATION_APPLY_PATTERN = re.compile(
    r"apply\s*for.{0,20}ration\s*card|new\s*ration\s*card|get\s*a\s*ration\s*card|"
    r"make\s*a\s*ration\s*card|ration\s*card\s*(?:banana|banwana|banane)|"
    r"नया\s*राशन\s*कार्ड|पुदிய\s*ரேஷன்\s*அட்டை",
    re.IGNORECASE,
)
RATION_FALSE_PATTERN = re.compile(
    r"no\s*ration\s*card|not\s*on\s*(?:the|my)\s*ration\s*card|राशन\s*कार्ड\s*नहीं",
    re.IGNORECASE,
)

INCOME_TAX_PATTERN = re.compile(
    r"pay\s*income\s*tax|income\s*tax\s*payer|आयकर\s*देता", re.IGNORECASE
)
GOVT_EMPLOYEE_PATTERN = re.compile(
    r"government\s*(?:job|employee)|सरकारी\s*नौकरी|அரசு\s*வேலை", re.IGNORECASE
)

EXISTING_PENSION_PATTERN = re.compile(
    r"already\s*(?:get|getting|receiv\w*)\s*(?:a\s*)?pension|"
    r"already\s*have\s*(?:a\s*)?pension",
    re.IGNORECASE,
)

SCHEME_KEYWORDS = {
    "pmkisan": ["kisan", "farmer", "farmland", "landholding", "किसान", "खेत", "விவசாயி", "நிலம்", "ஏக்கர்"],
    "pmayg": ["house", "housing", "pucca", "awaas", "आवास", "मकान", "வீடு"],
    "pmjay": ["ayushman", "jay", "hospital", "health insurance", "अस्पताल", "மருத்துவமனை", "காப்பீடு"],
    "cmchis": ["cmchis"],
    "pension": ["pension", "old age", "पेंशन", "ஓய்வூதியம்"],
}


def normalize_digits(text: str) -> str:
    return text.translate(DEVANAGARI_DIGITS).translate(TAMIL_DIGITS)


def detect_language(text: str) -> str:
    for ch in text:
        code = ord(ch)
        if 0x0B80 <= code <= 0x0BFF:
            return "ta"
        if 0x0900 <= code <= 0x097F:
            return "hi"
    return "en"


def _parse_income(raw_amount: str, multiplier_word: str | None) -> int:
    amount = int(raw_amount.replace(",", ""))
    if multiplier_word:
        word = multiplier_word.lower()
        if word in ("lakh", "lakhs", "लाख", "லட்சம்"):
            amount *= 100000
        elif word in ("thousand", "हज़ार", "ஆயிரம்"):
            amount *= 1000
    return amount


def extract_slots(text: str) -> dict:
    normalized = normalize_digits(text)
    slots: dict = {}

    age_match = AGE_PATTERN.search(normalized)
    if age_match:
        value = next(g for g in age_match.groups() if g)
        slots["age"] = int(value)

    land_match = LAND_PATTERN.search(normalized)
    if land_match:
        slots["land_size_acres"] = float(land_match.group(1))

    income_match = INCOME_PATTERN.search(normalized)
    if income_match:
        amount = _parse_income(income_match.group(1), income_match.group(2))
        period = (income_match.group(3) or "").lower()
        is_annual = period in ("year", "yearly", "annual", "साल", "वार्षिक", "ஆண்டு")
        slots["monthly_income"] = amount // 12 if is_annual else amount

    for alias, canonical in STATE_ALIASES.items():
        if alias in normalized.lower():
            slots["state"] = canonical
            break

    if BPL_TRUE_PATTERN.search(normalized):
        slots["is_bpl"] = True
    elif BPL_FALSE_PATTERN.search(normalized):
        slots["is_bpl"] = False

    if DESTITUTE_TRUE_PATTERN.search(normalized):
        slots["is_destitute"] = True
    elif DESTITUTE_FALSE_PATTERN.search(normalized):
        slots["is_destitute"] = False

    if PUCCA_FALSE_PATTERN.search(normalized):
        slots["has_pucca_house"] = False
    elif PUCCA_TRUE_PATTERN.search(normalized):
        slots["has_pucca_house"] = True

    if RATION_FALSE_PATTERN.search(normalized):
        slots["has_ration_card"] = False
    elif RATION_MENTION_PATTERN.search(normalized) and not RATION_APPLY_PATTERN.search(normalized):
        slots["has_ration_card"] = True

    if INCOME_TAX_PATTERN.search(normalized):
        slots["is_income_tax_payer"] = True

    if GOVT_EMPLOYEE_PATTERN.search(normalized):
        slots["is_government_employee"] = True

    if EXISTING_PENSION_PATTERN.search(normalized):
        slots["existing_benefits"] = ["a government pension"]

    return slots


def detect_candidate_schemes(text: str, state: str | None) -> list[str]:
    lowered = text.lower()
    candidates = []

    if any(kw in lowered for kw in SCHEME_KEYWORDS["pmkisan"]):
        candidates.append("pmkisan")
    if any(kw in lowered for kw in SCHEME_KEYWORDS["pmayg"]):
        candidates.append("pmayg")

    is_health_query = any(kw in lowered for kw in SCHEME_KEYWORDS["pmjay"]) or "cmchis" in lowered
    if is_health_query:
        if state and state.lower() == "tamil nadu":
            candidates.append("cmchis")
        else:
            candidates.append("pmjay")

    is_pension_query = any(kw in lowered for kw in SCHEME_KEYWORDS["pension"])
    if is_pension_query:
        if state and state.lower() == "tamil nadu":
            candidates.append("tnoap")
        else:
            candidates.append("nsap")

    return candidates


def next_question(profile: UserProfile, candidate_schemes: list[str], lang: str) -> tuple[str, str] | None:
    for scheme_id in candidate_schemes:
        missing = missing_slots(scheme_id, profile)
        if missing:
            slot = missing[0]
            question = QUESTIONS[slot].get(lang, QUESTIONS[slot]["en"])
            return slot, question
    return None


def detect_candidate_schemes_from_messages(messages: list[str], state: str | None) -> list[str]:
    combined = " ".join(messages)
    return detect_candidate_schemes(combined, state)


def process_turn(profile: UserProfile, message: str) -> dict:
    lang = detect_language(message)
    extracted = extract_slots(message)
    profile.merge(extracted)
    return {
        "language": lang,
        "extracted": extracted,
    }
