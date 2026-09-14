"""Provenance store.

Invariant: a document may only enter the corpus with a verifiable fetch record.
There is no code path that constructs a Document from model-generated text.
"""
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

STORE_DIR = Path("data/provenance")


class ProvenanceError(Exception):
    """Raised when a document cannot prove where it came from."""


@dataclass(frozen=True)
class FetchRecord:
    url: str
    http_status: int
    content_type: str
    method: str            # which acquisition rung produced this
    fetched_at: str        # ISO-8601 UTC
    sha256: str            # hash of the RAW bytes as served
    byte_length: int


@dataclass(frozen=True)
class Document:
    record: FetchRecord
    raw: bytes             # exactly what the server sent
    text: str              # extracted text; offsets in anchors index into THIS

    def __post_init__(self):
        if not self.record.sha256:
            raise ProvenanceError("document has no content hash")
        actual = hashlib.sha256(self.raw).hexdigest()
        if actual != self.record.sha256:
            raise ProvenanceError(
                f"hash mismatch: record says {self.record.sha256[:12]}, bytes are {actual[:12]}"
            )
        if not self.text.strip():
            raise ProvenanceError(f"no text extracted from {self.record.url}")

    @property
    def sha256(self) -> str:
        return self.record.sha256

    def slice(self, start: int, end: int) -> str:
        return self.text[start:end]


def make_document(raw: bytes, text: str, url: str, http_status: int,
                  content_type: str, method: str) -> Document:
    record = FetchRecord(
        url=url,
        http_status=http_status,
        content_type=content_type,
        method=method,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_length=len(raw),
    )
    return Document(record=record, raw=raw, text=text)


def save(doc: Document, store_dir: Path = STORE_DIR) -> Path:
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / f"{doc.sha256}.bin").write_bytes(doc.raw)
    (store_dir / f"{doc.sha256}.txt").write_text(doc.text, encoding="utf-8")
    meta_path = store_dir / f"{doc.sha256}.json"
    meta_path.write_text(json.dumps(asdict(doc.record), indent=2), encoding="utf-8")
    return meta_path


def load(sha256: str, store_dir: Path = STORE_DIR) -> Document:
    meta_path = store_dir / f"{sha256}.json"
    if not meta_path.exists():
        raise ProvenanceError(f"no fetch record for {sha256[:12]}")
    record = FetchRecord(**json.loads(meta_path.read_text(encoding="utf-8")))
    raw = (store_dir / f"{sha256}.bin").read_bytes()
    text = (store_dir / f"{sha256}.txt").read_text(encoding="utf-8")
    return Document(record=record, raw=raw, text=text)
