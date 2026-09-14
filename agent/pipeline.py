from agent.profile import UserProfile, scheme_id_from_clause_id
from agent.intake import process_turn, detect_candidate_schemes_from_messages, next_question
from agent.query_builder import build_query, GENERIC_QUERY
from agent.eligibility import check_eligibility, is_known_scheme, INSUFFICIENT_INFO
from agent.llm_reasoning import check_eligibility_via_llm
from agent.compose import compose
from agent.verify import verify
from agent.guardrails import redact_ids
from retrieval.retrieve import retrieve

HELPLINE_PLACEHOLDER = "1800-XXX-XXXX"
ESCALATION_MESSAGE = f"I can't confirm this from the scheme documents I have — here's the helpline: {HELPLINE_PLACEHOLDER}"
OUT_OF_CORPUS_MESSAGE = f"I don't have information on this in the scheme documents I have — here's the helpline: {HELPLINE_PLACEHOLDER}"
OUT_OF_CORPUS_THRESHOLD = 0.4691
CONFIRMATION_THRESHOLD = 0.35


def _rebuild_profile(history: list[str]) -> UserProfile:
    profile = UserProfile()
    for past_message in history:
        process_turn(profile, past_message)
    return profile


def _confirm_candidate_scheme(scheme_id: str, profile: UserProfile, mode: str) -> bool:
    query = build_query(profile)
    if query == GENERIC_QUERY:
        return False
    retrieve_state = profile.state if mode == "v2" and profile.state else ""
    hits = retrieve(query, state=retrieve_state, top_k=5)
    for hit in hits:
        if scheme_id_from_clause_id(hit["clause_id"]) == scheme_id:
            return hit["score"] >= CONFIRMATION_THRESHOLD
    return False


def _identify_scheme_via_retrieval(profile: UserProfile, mode: str) -> list[str] | None:
    query = build_query(profile)
    if query == GENERIC_QUERY:
        return None
    retrieve_state = profile.state if mode == "v2" and profile.state else ""
    hits = retrieve(query, state=retrieve_state, top_k=3)
    if not hits or hits[0]["score"] < OUT_OF_CORPUS_THRESHOLD:
        return []
    return [scheme_id_from_clause_id(hits[0]["clause_id"])]


def run_agent_turn(session_id: str, user_message: str, history: list[str], mode: str = "v2") -> dict:
    profile = _rebuild_profile(history)
    turn_info = process_turn(profile, user_message)

    candidate_schemes = detect_candidate_schemes_from_messages(
        history + [user_message], profile.state
    )

    if candidate_schemes and not _confirm_candidate_scheme(candidate_schemes[0], profile, mode):
        candidate_schemes = []

    if not candidate_schemes:
        retrieved_candidates = _identify_scheme_via_retrieval(profile, mode)
        if retrieved_candidates == []:
            reply = redact_ids(OUT_OF_CORPUS_MESSAGE, user_message)
            return {"reply": reply, "claims": [], "escalate": True}
        if retrieved_candidates:
            candidate_schemes = retrieved_candidates

    if not candidate_schemes:
        reply = "Could you tell me which government scheme you're asking about?"
        return {"reply": reply, "claims": [], "escalate": False}

    follow_up = next_question(profile, candidate_schemes, turn_info["language"])
    if follow_up:
        reply = redact_ids(follow_up[1], user_message)
        return {"reply": reply, "claims": [], "escalate": False}

    scheme_id = candidate_schemes[0]

    if is_known_scheme(scheme_id):
        eligibility_result = check_eligibility(scheme_id, profile)
    else:
        eligibility_result = check_eligibility_via_llm(scheme_id, profile)

    draft, claims = compose(eligibility_result, state=profile.state, mode=mode)

    if mode == "v2":
        supported_claims, _unsupported_claim_rate = verify(claims)
        if claims and len(supported_claims) < len(claims):
            reply = ESCALATION_MESSAGE
            escalate = True
            final_claims = []
        else:
            reply = draft
            escalate = eligibility_result.status == INSUFFICIENT_INFO
            final_claims = supported_claims
    else:
        reply = draft
        escalate = False
        final_claims = claims

    reply = redact_ids(reply, user_message)

    return {
        "reply": reply,
        "claims": [{"text": c.text, "clause_id": c.clause_id} for c in final_claims],
        "escalate": escalate,
    }
