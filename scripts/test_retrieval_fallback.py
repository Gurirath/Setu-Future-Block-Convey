from agent.pipeline import run_agent_turn
from agent.eligibility import check_eligibility, is_known_scheme
from agent.llm_reasoning import check_eligibility_via_llm
from agent.profile import UserProfile
from agent.intake import extract_slots

if __name__ == "__main__":
    print("=== Task 1: keyword-free scheme identification via retrieve() ===")
    msg = "I am 65 years old and live in Tamil Nadu"
    print(f"Input: {msg!r} (no scheme keyword present)")
    result = run_agent_turn("fallback-demo", msg, history=[], mode="v2")
    print(f"Output: {result}\n")

    print("=== Task 4: LLM-reasoning fallback, forced on a scheme check_eligibility already knows ===")
    print("(no real 7th scheme exists yet, so this simulates the fallback path directly on pmkisan's own real clauses)")
    profile = UserProfile()
    profile.merge(extract_slots("I own 3 acres of farmland"))
    print(f"is_known_scheme('pmkisan') = {is_known_scheme('pmkisan')}")
    result = check_eligibility_via_llm("pmkisan", profile)
    print(f"check_eligibility_via_llm result: {result}\n")

    print("=== Task 4: fallback when a scheme genuinely has zero documents ===")
    result = check_eligibility_via_llm("does_not_exist", profile)
    print(f"check_eligibility_via_llm('does_not_exist', ...) result: {result}")
