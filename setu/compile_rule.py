"""Compile an eligibility rule from anchored spans of a fetched document.

The model's only job is to READ text it was handed and emit a structured predicate.
It cannot invent an anchor: every anchor it returns must exactly match one of the
spans it was offered, or compilation fails. It cannot decide eligibility.
"""
import json

from setu.anchor import Span
from setu.providers import get_provider, ProviderUnavailable
from setu.rules import validate, RuleError, COMPARISONS

PROMPT = """You are given numbered excerpts from a government scheme document.

Excerpts:
{excerpts}

Convert ONLY the eligibility conditions stated in these excerpts into a JSON predicate.

Grammar:
  {{"op":"and"|"or","args":[...]}}
  {{"op":"not","args":[<one node>]}}
  {{"op":<comparison>,"field":<snake_case>,"value":<literal>,"span":<excerpt number>}}
  {{"op":"requires_authority","authority":"<the register or database that decides>","span":<excerpt number>}}

Comparisons available: {comparisons}

Rules you must follow:
- "span" must be the number of the excerpt that states that condition. Never invent one.
- If eligibility is decided by a database or official list rather than by stated
  criteria, use requires_authority.
- Encode only what the excerpts actually say. Omit anything not stated.
- Output raw JSON only. No markdown fence, no commentary.
"""

# Bounded-depth schema: the grammar is recursive, so this constrains the common
# shape without claiming to express arbitrary nesting.
LEAF_SCHEMA = {
    "type": "object",
    "properties": {
        "op": {"type": "string"},
        "field": {"type": "string"},
        "value": {},
        "authority": {"type": "string"},
        "span": {"type": "integer"},
    },
    "required": ["op"],
}
PREDICATE_SCHEMA = {
    "type": "object",
    "properties": {
        "op": {"type": "string"},
        "field": {"type": "string"},
        "value": {},
        "authority": {"type": "string"},
        "span": {"type": "integer"},
        "args": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": dict(LEAF_SCHEMA["properties"],
                                   args={"type": "array", "items": LEAF_SCHEMA}),
                "required": ["op"],
            },
        },
    },
    "required": ["op"],
}


class CompilationError(Exception):
    """Fails closed: no rule is better than a guessed rule."""


def _bind_spans(node, spans: list[Span], path="root"):
    """Replace the model's span INDEX with the real anchor. Indices are bounds-checked."""
    if not isinstance(node, dict):
        raise CompilationError(f"{path}: expected an object")
    op = node.get("op")
    if op in {"and", "or", "not"}:
        args = node.get("args")
        if not isinstance(args, list) or not args:
            raise CompilationError(f"{path}: '{op}' needs a non-empty args list")
        return {"op": op, "args": [_bind_spans(child, spans, f"{path}.{op}[{i}]")
                                   for i, child in enumerate(args)]}
    if "span" not in node:
        raise CompilationError(f"{path}: leaf cites no span, so it cannot be proven")
    index = node["span"]
    if not isinstance(index, int) or isinstance(index, bool) or not (0 <= index < len(spans)):
        raise CompilationError(
            f"{path}: cites excerpt {index!r}, but only 0..{len(spans) - 1} were offered"
        )
    bound = {key: value for key, value in node.items() if key != "span"}
    bound["anchor"] = spans[index].as_anchor()
    return bound


def compile_rule(spans: list[Span], provider=None) -> dict:
    if not spans:
        raise CompilationError("no spans were supplied; nothing can be compiled")

    if provider is None:
        try:
            provider = get_provider()
        except ProviderUnavailable as exc:
            raise CompilationError(str(exc)) from exc

    excerpts = "\n".join(f"[{i}] {span.text}" for i, span in enumerate(spans))
    prompt = PROMPT.format(excerpts=excerpts, comparisons=", ".join(sorted(COMPARISONS)))

    try:
        raw = provider.generate(prompt, schema=PREDICATE_SCHEMA)
    except Exception as exc:
        raise CompilationError(f"model call failed: {type(exc).__name__}: {exc}") from exc

    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CompilationError(f"model did not return valid JSON: {exc}") from exc

    rule = _bind_spans(parsed, spans)
    try:
        validate(rule)
    except RuleError as exc:
        raise CompilationError(f"compiled rule is structurally invalid: {exc}") from exc
    return rule
