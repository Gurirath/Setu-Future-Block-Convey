from retrieval.index import get_collection


def _to_dicts(result: dict) -> list[dict]:
    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    return [
        {
            "clause_id": ids[i],
            "scheme": metadatas[i]["scheme_name"],
            "text": documents[i],
            "score": 1 - distances[i],
        }
        for i in range(len(ids))
    ]


def retrieve(
    query: str,
    state: str,
    top_k: int = 3,
    persist_dir: str = "chroma_store",
) -> list[dict]:
    collection = get_collection(persist_dir)
    query_kwargs = {"query_texts": [query], "n_results": top_k}
    if state:
        query_kwargs["where"] = {"state": {"$in": [state, "central"]}}
    result = collection.query(**query_kwargs)
    return _to_dicts(result)


def get_clause(clause_id: str, persist_dir: str = "chroma_store") -> dict | None:
    collection = get_collection(persist_dir)
    result = collection.get(ids=[clause_id])
    if not result["ids"]:
        return None
    return {
        "clause_id": result["ids"][0],
        "scheme": result["metadatas"][0]["scheme_name"],
        "text": result["documents"][0],
    }
