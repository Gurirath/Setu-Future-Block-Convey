from retrieval.index import build_index

if __name__ == "__main__":
    count = build_index()
    print(f"Indexed {count} clauses into Chroma collection.")
