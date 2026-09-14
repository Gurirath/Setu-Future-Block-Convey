import time

from agent.eligibility import EligibilityResult, ELIGIBLE, NOT_ELIGIBLE, INSUFFICIENT_INFO
from agent.profile import UserProfile, scheme_id_from_clause_id
from agent.query_builder import build_query
from agent.llm_client import get_client, MODEL, record_llm_trace
from retrieval.retrieve import retrieve

FALLBACK_TOP_K = 5


def check_eligibility_via_llm(scheme_id: str, profile: UserProfile) -> EligibilityResult:
    query = build_query(profile)
    retrieve_state = profile.state or ""
    hits = retrieve(query, state=retrieve_state, top_k=FALLBACK_TOP_K)
    scheme_clauses = [h for h in hits if scheme_id_from_clause_id(h["clause_id"]) == scheme_id]

    if not scheme_clauses:
        return EligibilityResult(
            scheme_id, INSUFFICIENT_INFO,
            ["no scheme documents were retrieved for this scheme"], [],
        )

    client = get_client()
    if client is None:
        return EligibilityResult(
            scheme_id, INSUFFICIENT_INFO,
            ["no LLM reasoning backend is configured to evaluate this scheme"], [],
        )

    valid_ids = {c["clause_id"] for c in scheme_clauses}
    clause_lines = "\n".join(f"{c['clause_id']}: {c['text']}" for c in scheme_clauses)
    profile_lines = "\n".join(
        f"{key}: {value}" for key, value in profile.to_dict().items() if value not in (None, [], "")
    )

    prompt = (
        "Applicant profile:\n"
        f"{profile_lines}\n\n"
        "Scheme clauses (only these may be cited):\n"
        f"{clause_lines}\n\n"
        "Based only on the clauses above, is the applicant eligible for this scheme? "
        "Reply in exactly this format:\n"
        "STATUS: eligible OR not_eligible OR insufficient_info\n"
        "CLAUSE_ID: <one of the clause ids above, or NONE>\n"
        "REASON: <one sentence>"
    )

    messages = [{"role": "user", "content": prompt}]
    start = time.monotonic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=150,
            messages=messages,
        )
        text = response.content[0].text
        latency_ms = int((time.monotonic() - start) * 1000)
        record_llm_trace(MODEL, messages, text, latency_ms)
    except Exception:
        return EligibilityResult(scheme_id, INSUFFICIENT_INFO, ["LLM reasoning call failed"], [])

    status = INSUFFICIENT_INFO
    clause_id = None
    reason = "LLM reasoning response could not be parsed"

    for line in text.splitlines():
        upper = line.upper()
        if upper.startswith("STATUS:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in (ELIGIBLE, NOT_ELIGIBLE, INSUFFICIENT_INFO):
                status = value
        elif upper.startswith("CLAUSE_ID:"):
            value = line.split(":", 1)[1].strip()
            if value in valid_ids:
                clause_id = value
        elif upper.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    if status in (ELIGIBLE, NOT_ELIGIBLE) and clause_id is None:
        return EligibilityResult(
            scheme_id, INSUFFICIENT_INFO,
            ["LLM reasoning did not cite a real clause_id, so no claim can be bound"], [],
        )

    matched_clause_ids = [clause_id] if clause_id else []
    return EligibilityResult(scheme_id, status, [reason], matched_clause_ids)
