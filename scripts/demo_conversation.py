from agent.pipeline import run_agent_turn

CONVERSATION = [
    "I need help getting a pension",
    "I live in Tamil Nadu and I am 65 years old",
    "I have no regular income, my family doesn't support me either",
]


def run_mode(mode: str) -> None:
    print(f"--- mode={mode} ---")
    history = []
    for turn_number, message in enumerate(CONVERSATION, start=1):
        result = run_agent_turn("demo-session", message, history=list(history), mode=mode)
        print(f"Turn {turn_number} user: {message}")
        print(f"Turn {turn_number} agent: {result['reply']}")
        print(f"  claims={result['claims']} escalate={result['escalate']}")
        history.append(message)
    print()


if __name__ == "__main__":
    run_mode("v1")
    run_mode("v2")
