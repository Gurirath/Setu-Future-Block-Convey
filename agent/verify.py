import time

from agent.compose import Claim
from agent.llm_client import get_client, MODEL, record_llm_trace
from retrieval.retrieve import get_clause


def entails(premise: str, hypothesis: str) -> bool:
    client = get_client()
    if client is None:
        return False
    prompt = (
        "Scheme clause:\n"
        f"{premise}\n\n"
        "Claim:\n"
        f"{hypothesis}\n\n"
        "Does the scheme clause fully support this claim, with no unsupported facts "
        "added beyond what the clause states? Answer with exactly one word: YES or NO."
    )
    messages = [{"role": "user", "content": prompt}]
    start = time.monotonic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=5,
            messages=messages,
        )
        answer = response.content[0].text.strip().upper()
        latency_ms = int((time.monotonic() - start) * 1000)
        record_llm_trace(MODEL, messages, answer, latency_ms)
        return answer.startswith("YES")
    except Exception:
        return False


def verify(claims: list[Claim]) -> tuple[list[Claim], float]:
    supported = []
    for claim in claims:
        clause = get_clause(claim.clause_id)
        if clause is None:
            continue
        if entails(clause["text"], claim.text):
            supported.append(claim)

    total = len(claims)
    unsupported_claim_rate = 0.0 if total == 0 else (total - len(supported)) / total
    return supported, unsupported_claim_rate
