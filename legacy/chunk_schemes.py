from retrieval.chunk import chunk_all

if __name__ == "__main__":
    count = chunk_all()
    print(f"Chunked {count} clauses across scheme files.")
