"""The agent loop.

A session carries: what the user has told us, which source was resolved, the rule
compiled from that source, and the trace. Each turn advances exactly as far as the
evidence allows and then either answers, asks, or refuses.

Nothing here knows any scheme. The fields it asks about come from the rule compiled
from the fetched document; the language it asks in comes from the user's script.
"""
import json
import os
from dataclasses import dataclass, field

from setu import provenance
from setu.acquire import acquire, AcquisitionFailure
from setu.anchor import segment, rank, tokens
from setu.compile_rule import compile_rule, CompilationError
from setu.extract import detect_script, parse_value, expected_type
from setu.guardrails import redact, screen_source
from setu.resolve import resolve, ResolutionFailure
from setu.rules import evaluate, TRUE, UNKNOWN
from setu.trace import Tracer
from setu.verify import verify_claim

# Vocabulary that tends to mark eligibility passages in benefit documents. This is
# domain language, not scheme data, and it is overridable per deployment.
ANCHOR_HINTS = tuple(
    hint.strip() for hint in os.environ.get(
        "SETU_ANCHOR_HINTS",
        "eligibility,eligible,criteria,exclusion,excluded,qualify,applicant,age,income"
    ).split(",") if hint.strip()
)

ASK_PROMPT = """A person is checking whether they qualify for a government benefit.

To decide, one fact is still missing: "{field}"
The rule that needs it says: "{clause}"

Write one short, plain question asking them for that fact.
Write it in this language (ISO code): {language}
Use simple words. No preamble, no explanation, no quotes. Just the question.
"""

EXTRACT_PROMPT = """From the conversation below, extract any of these facts that the
person has actually stated.

Facts needed: {fields}

Conversation:
{conversation}

Return JSON only: an object mapping fact name to value. Use numbers for amounts,
true/false for yes-no facts, strings otherwise. Omit any fact the person has not
clearly stated. Never guess. If none are stated, return {{}}.
"""

SAY_PROMPT = """Rewrite this message in the language with ISO code {language}.
Keep it short, plain and literal. Return only the rewritten message.

Message: {message}
"""

SEARCH_PROMPT = """Translate this benefits question into English search keywords.
Return only the keywords, space separated. No punctuation, no explanation.

Question: {message}
"""


@dataclass
class AgentReply:
    kind: str                     # answer | question | refusal
    text: str
    language: str = "en"
    outcome: str = ""
    citations: list = field(default_factory=list)
    source_url: str = ""
    fetched_at: str = ""
    asked_field: str | None = None
    refusal_reason: str = ""
    trace_id: str = ""
    redactions: list = field(default_factory=list)


class Session:
    """One conversation. Reuses its resolved source and compiled rule across turns."""

    def __init__(self, provider, tracer: Tracer | None = None,
                 query_terms: list[str] | None = None, min_chars: int = 1000,
                 top_k: int = 12, candidates: list[str] | None = None,
                 anchor_hints: list[str] | None = None, min_hint_hits: int = 3):
        self.provider = provider
        self.tracer = tracer or Tracer()
        self.profile: dict = {}
        self.history: list[str] = []
        # None means "derive from what the user actually asked".
        self.query_terms = query_terms
        self.anchor_hints = list(ANCHOR_HINTS if anchor_hints is None else anchor_hints)
        self.candidates = candidates
        self.min_chars = min_chars
        self.min_hint_hits = min_hint_hits
        self.top_k = top_k
        self.doc = None
        self.rule = None
        self.resolution = None
        self.pending_field: str | None = None
        self.language = "en"
        self._search_cache: str | None = None

    # -- language helpers -------------------------------------------------
    def _say(self, message: str) -> str:
        """Render an English message in the user's language. Falls back to English."""
        if self.language == "en":
            return message
        try:
            out = self.provider.generate(
                SAY_PROMPT.format(language=self.language, message=message), schema=None)
            return (out or "").strip() or message
        except Exception:
            return message

    def _search_terms(self, query: str) -> list[str]:
        """Terms to retrieve with.

        Source documents are overwhelmingly in English, so a query in another
        script has zero lexical overlap with them no matter how well it tokenises.
        Translating the query for retrieval is what makes non-English input work;
        the user still sees every reply in their own language.
        """
        if self.query_terms:
            return list(self.query_terms)
        if self.language == "en":
            return [query]
        if self._search_cache is None:
            try:
                out = self.provider.generate(
                    SEARCH_PROMPT.format(message=query), schema=None)
                self._search_cache = (out or "").strip()
            except Exception:
                self._search_cache = ""
        # Keep the original too: proper nouns often survive transliteration.
        return [self._search_cache, query] if self._search_cache else [query]

    def _ask_text(self, field_name: str, clause: str) -> str:
        try:
            out = self.provider.generate(
                ASK_PROMPT.format(field=field_name.replace("_", " "),
                                  clause=clause[:300], language=self.language),
                schema=None)
            question = (out or "").strip()
            if question:
                return question
        except Exception:
            pass
        return self._say(f"Could you tell me your {field_name.replace('_', ' ')}?")

    # -- source sufficiency -----------------------------------------------
    def _is_usable(self, doc) -> bool:
        """A source is sufficient when it actually contains eligibility language.

        Length alone is the wrong test: a portal landing page is long enough while
        being pure navigation, so the ladder would stop there and never reach the
        guidelines PDF linked from it. Requiring eligibility vocabulary makes the
        ladder escalate until it finds a document worth compiling from.
        """
        if len(doc.text) < self.min_chars:
            return False
        found = tokens(doc.text)
        hits = sum(1 for hint in self.anchor_hints if hint.lower() in found)
        return hits >= self.min_hint_hits

    # -- fact gathering ---------------------------------------------------
    def _clause_for(self, field_name: str) -> str:
        """The anchored text of the leaf that needs this field."""
        found = []

        def walk(node):
            if node.get("op") in {"and", "or", "not"}:
                for child in node["args"]:
                    walk(child)
            elif node.get("field") == field_name and self.doc is not None:
                anchor = node["anchor"]
                found.append(self.doc.slice(anchor["start"], anchor["end"]))

        if self.rule:
            walk(self.rule)
        return found[0] if found else ""

    def _leaf_value_for(self, field_name):
        """The literal the rule compares this field against, for type inference."""
        found = []

        def walk(node):
            if node.get("op") in {"and", "or", "not"}:
                for child in node["args"]:
                    walk(child)
            elif node.get("field") == field_name and "value" in node:
                found.append(node["value"])

        if self.rule:
            walk(self.rule)
        return found[0] if found else None

    def _extract_facts(self, needed: list[str]) -> dict:
        """Ask the model to pull stated facts out of the conversation. Never guesses."""
        if not needed:
            return {}
        try:
            raw = self.provider.generate(
                EXTRACT_PROMPT.format(fields=", ".join(needed),
                                      conversation="\n".join(self.history[-8:])),
                schema=None)
            raw = (raw or "").strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].removeprefix("json").strip()
            parsed = json.loads(raw)
        except Exception:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {k: v for k, v in parsed.items() if k in needed and v is not None}

    # -- the turn ---------------------------------------------------------
    def turn(self, message: str) -> AgentReply:
        tracer = self.tracer
        screening = redact(message)
        self.language = detect_script(message)
        self.history.append(screening.text)
        terms = self._search_terms(" ".join(self.history))

        with tracer.span("turn", language=self.language,
                         redactions=screening.redactions) as turn_span:

            if screening.injection_detected:
                tracer.set(turn_span, refused="prompt_injection")
                return AgentReply("refusal",
                                  self._say("I can only answer from official scheme "
                                            "documents, so I cannot follow instructions "
                                            "given in a message."),
                                  language=self.language,
                                  refusal_reason="instruction-shaped input rejected",
                                  trace_id=tracer.trace_id,
                                  redactions=screening.redactions)

            # If we asked for something, try to read the answer to it first.
            if self.pending_field:
                expected = expected_type(self._leaf_value_for(self.pending_field))
                value = parse_value(screening.text, expected)
                if value is not None:
                    self.profile[self.pending_field] = value
                    tracer.set(turn_span, filled=self.pending_field)
                    self.pending_field = None

            # 1. RESOLVE -- find the governing document, once per session
            if self.resolution is None:
                try:
                    with tracer.span("resolve", query=screening.text[:120]):
                        self.resolution = resolve(
                            screening.text, terms, self.provider,
                            candidates=self.candidates)
                except ResolutionFailure as exc:
                    return self._refuse("I could not find an official source that covers "
                                        "this, so I have nothing to check against.",
                                        str(exc), screening)

            # 2. ACQUIRE -- fetch once, reuse within the session
            if self.doc is None:
                try:
                    with tracer.span("acquire", url=self.resolution.url) as sp:
                        self.doc = acquire(
                            self.resolution.url, sufficient=self._is_usable)
                        tracer.set(sp, sha256=self.doc.sha256,
                                   method=self.doc.record.method, chars=len(self.doc.text))
                        provenance.save(self.doc)
                except AcquisitionFailure as exc:
                    return self._refuse("I could not open the official source, so I have "
                                        "nothing I can prove an answer against.",
                                        str(exc), screening)

                if screen_source(self.doc.text):
                    return self._refuse("The page I fetched contains instruction-shaped "
                                        "text, so I will not derive rules from it.",
                                        "source failed injection screening", screening)

            # 3. COMPILE -- once per document
            if self.rule is None:
                with tracer.span("anchor") as sp:
                    spans = segment(self.doc)
                    ranked = [s for s, _ in rank(spans, list(terms) + self.anchor_hints,
                                                 top_k=self.top_k)]
                    tracer.set(sp, total_spans=len(spans), selected=len(ranked))
                if not ranked:
                    return self._refuse("I opened the official source but found no passage "
                                        "relevant to your question.",
                                        "no span matched the query terms", screening)
                try:
                    with tracer.span("compile", spans_offered=len(ranked)):
                        self.rule = compile_rule(ranked, provider=self.provider)
                except CompilationError as exc:
                    return self._refuse("I could not derive a checkable rule from the "
                                        "official source, so I will not guess.",
                                        str(exc), screening)

            # 4. GATHER -- pull any stated facts the rule still needs
            ev = evaluate(self.rule, self.profile)
            if ev.unknown_fields:
                with tracer.span("extract", needed=ev.unknown_fields) as sp:
                    facts = self._extract_facts(ev.unknown_fields)
                    self.profile.update(facts)
                    tracer.set(sp, extracted=sorted(facts))

            # 5. ADJUDICATE -- pure, deterministic
            with tracer.span("adjudicate") as sp:
                ev = evaluate(self.rule, self.profile)
                tracer.set(sp, value=ev.value, unknown=ev.unknown_fields,
                           fired=len(ev.fired),
                           authorities=[a["authority"] for a in ev.authorities])

            if ev.value == UNKNOWN:
                if ev.authorities:
                    names = ", ".join(a["authority"] for a in ev.authorities)
                    return self._refuse(
                        "Your eligibility here is decided by an official register "
                        f"({names}), not by published criteria. I cannot determine it "
                        "from any document.",
                        f"decided by authority: {names}", screening)
                self.pending_field = ev.unknown_fields[0]
                question = self._ask_text(self.pending_field,
                                          self._clause_for(self.pending_field))
                tracer.set(turn_span, asked=self.pending_field)
                return AgentReply("question", question, language=self.language,
                                  asked_field=self.pending_field,
                                  source_url=self.resolution.url,
                                  fetched_at=self.doc.record.fetched_at,
                                  trace_id=tracer.trace_id,
                                  redactions=screening.redactions)

            # 6. VERIFY -- every citation must resolve to real text
            citations = []
            with tracer.span("verify", claims=len(ev.fired)) as sp:
                for fired in ev.fired:
                    result = verify_claim(fired["field"].replace("_", " "),
                                          fired["anchor"], self.doc, min_coverage=0.0)
                    if not result.ok:
                        tracer.set(sp, failed_on=fired["field"])
                        return self._refuse(
                            "I reached a conclusion but could not tie it back to the "
                            "source, so I am discarding it.", result.reason, screening)
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
            tracer.set(turn_span, outcome=outcome)
            return AgentReply(
                "answer",
                self._say(f"Based on the official source I just read, you {verb} the "
                          "stated conditions."),
                language=self.language, outcome=outcome, citations=citations,
                source_url=self.resolution.url, fetched_at=self.doc.record.fetched_at,
                trace_id=tracer.trace_id, redactions=screening.redactions)

    def _refuse(self, message: str, reason: str, screening) -> AgentReply:
        return AgentReply("refusal", self._say(message), language=self.language,
                          refusal_reason=reason,
                          source_url=self.resolution.url if self.resolution else "",
                          fetched_at=self.doc.record.fetched_at if self.doc else "",
                          trace_id=self.tracer.trace_id,
                          redactions=screening.redactions)
