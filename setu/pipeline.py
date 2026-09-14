"""End-to-end orchestration: acquire -> anchor -> compile -> adjudicate -> verify.

Every exit is either a grounded answer carrying its source, or an explicit refusal
carrying the reason. There is no third path.
"""
from dataclasses import dataclass, field

from setu import provenance
from setu.acquire import acquire, AcquisitionFailure
from setu.anchor import segment, rank
from setu.compile_rule import compile_rule, CompilationError
from setu.rules import evaluate, next_unknown_field, TRUE, UNKNOWN
from setu.trace import Tracer
from setu.verify import verify_claim


@dataclass
class Answer:
    outcome: str                      # eligible | not_eligible | need_more_info | refused
    message: str
    source_url: str = ""
    fetched_at: str = ""
    citations: list[dict] = field(default_factory=list)
    ask_for: str | None = None
    refusal_reason: str = ""
    trace_id: str = ""


def _sufficient(min_chars: int):
    def check(doc):
        return len(doc.text) >= min_chars
    return check


def answer(source_url: str, profile: dict, query_terms: list[str],
           tracer: Tracer | None = None, min_chars: int = 1000,
           top_k: int = 12, provider=None) -> Answer:
    tracer = tracer or Tracer()

    # 1. ACQUIRE -- real bytes or nothing
    try:
        with tracer.span("acquire", url=source_url) as sp:
            doc = acquire(source_url, sufficient=_sufficient(min_chars))
            tracer.set(sp, sha256=doc.sha256, method=doc.record.method, chars=len(doc.text))
            provenance.save(doc)
    except AcquisitionFailure as exc:
        return Answer("refused",
                      "I could not open the official source for this scheme, so I have "
                      "nothing I can prove an answer against.",
                      source_url=source_url, refusal_reason=str(exc),
                      trace_id=tracer.trace_id)

    # 2. ANCHOR -- locate candidate passages by exact offset
    with tracer.span("anchor") as sp:
        spans = segment(doc)
        ranked = [s for s, _score in rank(spans, query_terms, top_k=top_k)]
        tracer.set(sp, total_spans=len(spans), selected=len(ranked))
    if not ranked:
        return Answer("refused",
                      "I opened the official source but could not locate any passage "
                      "relevant to your question.",
                      source_url=source_url, fetched_at=doc.record.fetched_at,
                      refusal_reason="no span matched the query terms",
                      trace_id=tracer.trace_id)

    # 3. COMPILE -- rule derived from the fetched text, never from built-in knowledge
    try:
        with tracer.span("compile", spans_offered=len(ranked)) as sp:
            rule = compile_rule(ranked, provider=provider)
            tracer.set(sp, compiled=True)
    except CompilationError as exc:
        return Answer("refused",
                      "I could not derive a checkable eligibility rule from the official "
                      "source, so I will not guess.",
                      source_url=source_url, fetched_at=doc.record.fetched_at,
                      refusal_reason=str(exc), trace_id=tracer.trace_id)

    # 4. ADJUDICATE -- pure, deterministic, no model involved
    with tracer.span("adjudicate") as sp:
        ev = evaluate(rule, profile)
        tracer.set(sp, value=ev.value, unknown_fields=ev.unknown_fields,
                   fired=len(ev.fired),
                   authorities=[a["authority"] for a in ev.authorities])

    if ev.value == UNKNOWN:
        if ev.authorities:
            names = ", ".join(a["authority"] for a in ev.authorities)
            return Answer("refused",
                          "Your eligibility here is not decided by published criteria but "
                          f"by an official register ({names}). I cannot determine it from "
                          "any document, and neither can any system that does not query "
                          "that register.",
                          source_url=source_url, fetched_at=doc.record.fetched_at,
                          refusal_reason=f"decided by authority: {names}",
                          trace_id=tracer.trace_id)
        return Answer("need_more_info",
                      "I need one more detail before I can answer.",
                      source_url=source_url, fetched_at=doc.record.fetched_at,
                      ask_for=next_unknown_field(rule, profile),
                      trace_id=tracer.trace_id)

    # 5. VERIFY -- every citation must resolve to real text in the fetched document
    citations = []
    with tracer.span("verify", claims=len(ev.fired)) as sp:
        for fired in ev.fired:
            result = verify_claim(fired["field"].replace("_", " "), fired["anchor"],
                                  doc, min_coverage=0.0)
            if not result.ok:
                tracer.set(sp, failed_on=fired["field"], reason=result.reason)
                return Answer("refused",
                              "I reached a conclusion but could not tie it back to the "
                              "source text, so I am discarding it rather than showing it "
                              "to you.",
                              source_url=source_url, fetched_at=doc.record.fetched_at,
                              refusal_reason=result.reason, trace_id=tracer.trace_id)
            citations.append({
                "condition": f"{fired['field']} {fired['op']} {fired['value']}",
                "your_value": fired["actual"],
                "satisfied": fired["result"],
                "is_exclusion": fired.get("negated", False),
                "helps_you": fired.get("helps", fired["result"]),
                "quote": result.quote,
                "anchor": fired["anchor"],
            })
        tracer.set(sp, verified=len(citations))

    outcome = "eligible" if ev.value == TRUE else "not_eligible"
    verb = "appear to meet" if ev.value == TRUE else "do not meet"
    return Answer(outcome,
                  f"Based on the official source I just read, you {verb} the stated "
                  "conditions.",
                  source_url=source_url, fetched_at=doc.record.fetched_at,
                  citations=citations, trace_id=tracer.trace_id)
