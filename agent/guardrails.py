import re

DIGIT_RUN_PATTERN = re.compile(r"\b\d[\d\-\s]{7,}\d\b")
ALPHANUMERIC_CODE_PATTERN = re.compile(r"\b[A-Za-z]{2,5}-[A-Za-z0-9]{1,5}-\d{4,}\b")
PAN_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


def find_id_like_tokens(user_message: str) -> list[str]:
    tokens = []
    tokens.extend(DIGIT_RUN_PATTERN.findall(user_message))
    tokens.extend(ALPHANUMERIC_CODE_PATTERN.findall(user_message))
    tokens.extend(PAN_PATTERN.findall(user_message.upper()))
    return tokens


def redact_ids(reply: str, user_message: str) -> str:
    redacted = reply
    for token in find_id_like_tokens(user_message):
        if token in redacted:
            redacted = redacted.replace(token, "[ID redacted]")
    return redacted
