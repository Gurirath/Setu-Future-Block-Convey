"""Span tracing. Every stage emits a span; any verdict is replayable from its trace."""
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

TRACE_DIR = Path(os.environ.get("SETU_TRACE_DIR", "traces"))


class Tracer:
    def __init__(self, trace_id: str | None = None, sink: Path | None = None):
        self.trace_id = trace_id or uuid.uuid4().hex[:12]
        self.spans: list[dict] = []
        self._stack: list[str] = []
        self._sink = sink

    @contextmanager
    def span(self, name: str, **attrs):
        span = {
            "trace_id": self.trace_id,
            "span_id": uuid.uuid4().hex[:8],
            "parent_id": self._stack[-1] if self._stack else None,
            "name": name,
            "start": time.time(),
            "attrs": dict(attrs),
            "status": "ok",
        }
        self._stack.append(span["span_id"])
        try:
            yield span
        except Exception as exc:
            span["status"] = "error"
            span["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._stack.pop()
            span["duration_ms"] = round((time.time() - span["start"]) * 1000, 2)
            self.spans.append(span)

    def set(self, span: dict, **attrs):
        span["attrs"].update(attrs)

    def flush(self) -> Path | None:
        sink = self._sink
        if sink is None:
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            sink = TRACE_DIR / f"{self.trace_id}.jsonl"
        with sink.open("w", encoding="utf-8") as fh:
            for span in self.spans:
                fh.write(json.dumps(span, ensure_ascii=False, default=str) + "\n")
        return sink
