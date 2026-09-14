import csv

from agent.pipeline import run_agent_turn, OUT_OF_CORPUS_MESSAGE

if __name__ == "__main__":
    with open("data/golden_set.csv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["category"] == "out_of_corpus"]

    for row in rows:
        result = run_agent_turn(f"ooc-{row['id']}", row["query"], history=[], mode="v2")
        routed_correctly = result["reply"] == OUT_OF_CORPUS_MESSAGE
        print(f"[{row['id']}] routed_to_out_of_corpus={routed_correctly}  escalate={result['escalate']}")
        print(f"      query: {row['query']}")
        print(f"      reply: {result['reply']}")
        print()
