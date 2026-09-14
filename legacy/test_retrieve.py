from retrieval.retrieve import retrieve

TEST_CASES = [
    {"query": "I own farmland, will I get income support money from the government?", "state": ""},
    {"query": "Can I get a pension if I am 65 and have no income?", "state": "Tamil Nadu"},
    {"query": "I am a woman and the head of my ration card family in Chennai, is there a monthly assistance scheme for me?", "state": "Tamil Nadu"},
    {"query": "Free health insurance for hospital treatment for poor families", "state": "Maharashtra"},
]

if __name__ == "__main__":
    for case in TEST_CASES:
        print(f"Query: {case['query']!r}  (state={case['state'] or 'none'})")
        for hit in retrieve(case["query"], state=case["state"], top_k=3):
            print(f"  {hit['clause_id']:14} score={hit['score']:.3f}  [{hit['scheme']}]  {hit['text'][:90]}")
        print()
