from dataclasses import dataclass

from agent.eligibility import EligibilityResult, ELIGIBLE, NOT_ELIGIBLE
from agent.profile import SCHEME_NAMES, scheme_id_from_clause_id
from retrieval.retrieve import retrieve

SUPPLEMENTARY_QUERY = "benefit amount required documents exclusion criteria"
SUPPLEMENTARY_LIMIT = 2
SUPPLEMENTARY_TOP_K = 5


@dataclass
class Claim:
    text: str
    clause_id: str


def _supplementary_claims(
    scheme_id: str, state: str | None, existing_clause_ids: set, mode: str,
) -> list[Claim]:
    retrieve_state = state if mode == "v2" and state else ""
    hits = retrieve(SUPPLEMENTARY_QUERY, state=retrieve_state, top_k=SUPPLEMENTARY_TOP_K)

    supplementary = []
    for hit in hits:
        if scheme_id_from_clause_id(hit["clause_id"]) != scheme_id:
            continue
        if hit["clause_id"] in existing_clause_ids:
            continue
        supplementary.append(Claim(text=hit["text"], clause_id=hit["clause_id"]))
        if len(supplementary) >= SUPPLEMENTARY_LIMIT:
            break
    return supplementary


def compose(
    eligibility_result: EligibilityResult, state: str | None = None, mode: str = "v2",
) -> tuple[str, list[Claim]]:
    scheme_name = SCHEME_NAMES.get(eligibility_result.scheme_id, eligibility_result.scheme_id)
    reason_text = "; ".join(eligibility_result.reasons)

    if eligibility_result.status == ELIGIBLE:
        draft = f"Based on {', '.join(eligibility_result.matched_clause_ids)}, you appear eligible for {scheme_name}: {reason_text}."
        claims = [Claim(text=reason_text, clause_id=cid) for cid in eligibility_result.matched_clause_ids]
        claims += _supplementary_claims(
            eligibility_result.scheme_id, state, set(eligibility_result.matched_clause_ids), mode,
        )
        return draft, claims

    if eligibility_result.status == NOT_ELIGIBLE:
        draft = f"Based on {', '.join(eligibility_result.matched_clause_ids)}, you do not appear eligible for {scheme_name}: {reason_text}."
        claims = [Claim(text=reason_text, clause_id=cid) for cid in eligibility_result.matched_clause_ids]
        claims += _supplementary_claims(
            eligibility_result.scheme_id, state, set(eligibility_result.matched_clause_ids), mode,
        )
        return draft, claims

    draft = f"I don't have enough information yet to determine your eligibility for {scheme_name}: {reason_text}."
    return draft, []
