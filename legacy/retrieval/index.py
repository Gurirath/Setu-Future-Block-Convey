import json
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "setu_scheme_clauses"


def get_chroma_client(persist_dir: str = "chroma_store") -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=persist_dir)


def get_embedding_function() -> SentenceTransformerEmbeddingFunction:
    return SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL_NAME)


_collection_cache: dict = {}


def get_collection(persist_dir: str = "chroma_store"):
    if persist_dir in _collection_cache:
        return _collection_cache[persist_dir]
    client = get_chroma_client(persist_dir)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )
    _collection_cache[persist_dir] = collection
    return collection


def load_chunked_schemes(schemes_dir: str = "data/schemes") -> list[dict]:
    files = sorted(Path(schemes_dir).glob("*.json"))
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def build_index(
    schemes_dir: str = "data/schemes",
    persist_dir: str = "chroma_store",
    reset: bool = True,
) -> int:
    client = get_chroma_client(persist_dir)
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )

    schemes = load_chunked_schemes(schemes_dir)
    ids, documents, metadatas = [], [], []
    for scheme in schemes:
        for clause in scheme["clauses"]:
            ids.append(clause["clause_id"])
            documents.append(clause["text"])
            metadata = {
                "clause_id": clause["clause_id"],
                "scheme_id": scheme["scheme_id"],
                "scheme_name": scheme["scheme_name"],
                "state": scheme["state"],
                "section_title": clause["section_title"],
                "clause_type": clause["clause_type"],
            }
            if "last_verified" in scheme:
                metadata["last_verified"] = scheme["last_verified"]
            metadatas.append(metadata)

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)
