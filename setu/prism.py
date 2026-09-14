"""PRISM export.

Maps this agent's spans onto PRISM's trajectory step schema and submits them.

Two rules:
  - Observability must never change behaviour. If PRISM is unconfigured, down, or
    rejects a payload, the agent still answers. Export failures are reported, not raised.
  - Nothing invented. A step reports what its span actually recorded.
"""
import os
from dataclasses import dataclass

# Our span vocabulary -> PRISM's step vocabulary. This describes our own pipeline,
# not any scheme.
STEP_MAP = {
    "resolve":    ("tool_call", "resolve_source"),
    "acquire":    ("tool_call", "fetch_document"),
    "anchor":     ("reasoning", None),
    "compile":    ("reasoning", None),
    "extract":    ("reasoning", None),
    "adjudicate": ("reasoning", None),
    "verify":     ("reasoning", None),
    "turn":       ("final_answer", None),
}

CONCLUSIONS = {
    "anchor":     lambda a: f"selected {a.get('selected', 0)} candidate clauses from "
                            f"{a.get('total_spans', 0)} segments",
    "compile":    lambda a: f"compiled a predicate from {a.get('spans_offered', 0)} "
                            f"offered excerpts; anchors bound to the fetched document",
    "adjudicate": lambda a: f"deterministic verdict={a.get('value', '?')} from "
                            f"{a.get('fired', 0)} matched conditions"
                            + (f"; unresolved: {a.get('unknown')}" if a.get('unknown') else ""),
    "verify":     lambda a: f"{a.get('verified', 0)} of {a.get('claims', 0)} citations "
                            f"resolved to real text at their anchors",
    "acquire":    lambda a: f"fetched {a.get('chars', 0)} chars via {a.get('method', '?')}; "
                            f"content hash {str(a.get('sha256', ''))[:12]}",
    "resolve":    lambda a: f"verified source for query {str(a.get('query', ''))[:60]!r}",
    "extract":    lambda a: f"read {a.get('extracted', 'no')} facts from the conversation",
}

LABELS = {
    "resolve":    "Locate the governing official document",
    "acquire":    "Fetch the source and pin its content hash",
    "anchor":     "Segment the document and select candidate clauses",
    "compile":    "Compile an eligibility rule from the fetched text",
    "extract":    "Read stated facts out of the conversation",
    "adjudicate": "Evaluate the rule deterministically",
    "verify":     "Check every citation resolves to real source text",
    "turn":       "Reply to the user",
}


class PrismUnconfigured(Exception):
    """No PRISM credentials. Export is skipped, never faked."""


def read_credential(suffix: str) -> str | None:
    """Accept both the SDK's PRISMTRACE_* names and the shorter PRISM_* form."""
    return os.environ.get(f"PRISMTRACE_{suffix}") or os.environ.get(f"PRISM_{suffix}")


_llm_client: list = []


def llm_client():
    """Lazily built shared client for per-call LLM traces. None when unconfigured."""
    if _llm_client:
        return _llm_client[0]
    api_key = read_credential("API_KEY")
    host = read_credential("HOST")
    project_id = read_credential("PROJECT_ID")
    client = None
    if api_key and host and project_id:
        try:
            from prismtrace import PRISMtrace
            client = PRISMtrace(api_key=api_key, host=host, project_id=project_id)
        except Exception:
            client = None
    _llm_client.append(client)
    return client


def record_llm(model: str, prompt: str, output: str, latency_ms: int,
               agent_name: str = "setu-eligibility-agent") -> bool:
    """Record one model call. Never raises and never changes behaviour.

    Every model call in this project funnels through Provider.generate, so wiring
    this one chokepoint covers all of them -- including any call site added later.
    """
    client = llm_client()
    if client is None:
        return False
    try:
        client.trace_llm(
            model=model,
            input_messages=[{"role": "user", "content": prompt[:4000]}],
            output=(output or "")[:4000],
            latency_ms=int(latency_ms),
            agent_name=agent_name,
        )
        return True
    except Exception:
        return False


def _summarise(attrs: dict) -> str:
    if not attrs:
        return ""
    parts = []
    for key, value in attrs.items():
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value) or "none"
        text = str(value)
        parts.append(f"{key}={text[:80]}")
    return "; ".join(parts)[:500]


def _completed_at(span: dict):
    """Sort key for completion order.

    `seq` is assigned when a span closes, so it is exact. The clock-based value is
    only a fallback for spans from a tracer that did not record one.
    """
    if "seq" in span:
        return (0, span["seq"])
    return (1, span.get("start", 0) + (span.get("duration_ms", 0) or 0) / 1000.0)


def spans_to_steps(spans: list[dict]) -> list[dict]:
    """Convert tracer spans to PRISM steps, ordered by COMPLETION.

    Ordering by start time puts the outer `turn` span first, which reads as a
    final answer emitted before any work happened. The turn is the span that
    finishes last, so completion order is what reflects the real sequence.
    """
    steps = []
    for span in sorted(spans, key=_completed_at):
        name = span.get("name", "")
        step_type, tool_name = STEP_MAP.get(name, ("reasoning", None))
        attrs = span.get("attrs", {})
        conclusion = CONCLUSIONS.get(name)
        summary = conclusion(attrs) if conclusion else _summarise(attrs)
        if conclusion and attrs:
            summary = f"{summary} [{_summarise(attrs)}]"[:500]
        step = {
            "step_type": step_type,
            "label": LABELS.get(name, name),
            "output_summary": summary,
            "status": "error" if span.get("status") == "error" else "success",
        }
        if span.get("duration_ms") is not None:
            step["duration_ms"] = int(span["duration_ms"])
        if tool_name:
            step["tool_name"] = tool_name
        if span.get("error"):
            step["output_summary"] = (step["output_summary"] + " | " + span["error"])[:500]
        steps.append(step)
    return steps


@dataclass
class ExportResult:
    ok: bool
    trajectory_id: str = ""
    step_count: int = 0
    reason: str = ""


class PrismExporter:
    def __init__(self, client, agent_name: str = "setu-eligibility-agent"):
        self.client = client
        self.agent_name = agent_name

    @classmethod
    def from_env(cls, agent_name: str = "setu-eligibility-agent"):
        # The SDK ships as prismtrace, and its dashboard hands out PRISMTRACE_*
        # names. Accept both spellings rather than making the caller rename.
        api_key = read_credential("API_KEY")
        host = read_credential("HOST")
        project_id = read_credential("PROJECT_ID")
        missing = [f"PRISMTRACE_{name}" for name, value in
                   (("API_KEY", api_key), ("HOST", host),
                    ("PROJECT_ID", project_id)) if not value]
        if missing:
            raise PrismUnconfigured("missing " + ", ".join(missing))
        from prismtrace import PRISMtrace
        return cls(PRISMtrace(api_key=api_key, host=host, project_id=project_id),
                   agent_name=agent_name)

    def export(self, tracer, conversation_id: str | None = None,
               final_status: str = "success", model: str | None = None) -> ExportResult:
        steps = spans_to_steps(tracer.spans)
        if not steps:
            return ExportResult(False, reason="no spans to export")
        try:
            response = self.client.submit_trajectory(
                steps,
                agent_name=self.agent_name,
                conversation_id=conversation_id or tracer.trace_id,
                request_id=tracer.trace_id,
                model=model,
                final_status=final_status,
            )
        except Exception as exc:
            return ExportResult(False, reason=f"{type(exc).__name__}: {exc}")
        if not response:
            return ExportResult(False, step_count=len(steps),
                                reason="PRISM returned no response")
        trajectory_id = (response.get("trajectory_id") or response.get("id") or "")
        return ExportResult(True, trajectory_id=str(trajectory_id),
                            step_count=response.get("step_count", len(steps)))

    def evaluation(self, trajectory_id: str) -> dict | None:
        try:
            return self.client.get_trajectory_evaluation(trajectory_id)
        except Exception:
            return None

    def flush(self) -> None:
        try:
            self.client.flush()
        except Exception:
            pass
