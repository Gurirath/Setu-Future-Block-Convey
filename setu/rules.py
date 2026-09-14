"""Runtime-compiled eligibility rules.

A rule is DATA derived from a fetched document, never code written here.
Every leaf carries an anchor: (doc_sha256, start, end) into that document's text.

Evaluation is three-valued (Kleene). Missing user data yields UNKNOWN, never False --
"I don't know" must never masquerade as "you don't qualify".
"""
from dataclasses import dataclass, field

TRUE, FALSE, UNKNOWN = "true", "false", "unknown"

COMPARISONS = {
    "eq":     lambda a, b: a == b,
    "ne":     lambda a, b: a != b,
    "gt":     lambda a, b: a > b,
    "gte":    lambda a, b: a >= b,
    "lt":     lambda a, b: a < b,
    "lte":    lambda a, b: a <= b,
    "in":     lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}
BOOLEAN_OPS = {"and", "or", "not"}
AUTHORITY_OP = "requires_authority"


class RuleError(Exception):
    """Raised when a compiled rule is structurally invalid. Fails closed."""


@dataclass
class Anchor:
    doc_sha256: str
    start: int
    end: int

    def quote(self, doc) -> str:
        return doc.slice(self.start, self.end)


@dataclass
class Evaluation:
    value: str
    fired: list[dict] = field(default_factory=list)      # leaves that determined the outcome
    unknown_fields: list[str] = field(default_factory=list)
    authorities: list[dict] = field(default_factory=list)


def validate(node, path="root") -> None:
    if not isinstance(node, dict):
        raise RuleError(f"{path}: node must be an object, got {type(node).__name__}")
    op = node.get("op")
    if op is None:
        raise RuleError(f"{path}: node has no 'op'")

    if op in BOOLEAN_OPS:
        args = node.get("args")
        if not isinstance(args, list) or not args:
            raise RuleError(f"{path}: '{op}' needs a non-empty 'args' list")
        if op == "not" and len(args) != 1:
            raise RuleError(f"{path}: 'not' takes exactly one argument, got {len(args)}")
        for i, child in enumerate(args):
            validate(child, f"{path}.{op}[{i}]")
        return

    if op == AUTHORITY_OP:
        if not node.get("authority"):
            raise RuleError(f"{path}: '{AUTHORITY_OP}' needs an 'authority'")
        _validate_anchor(node, path)
        return

    if op not in COMPARISONS:
        raise RuleError(f"{path}: unknown op '{op}'")
    if not node.get("field"):
        raise RuleError(f"{path}: comparison needs a 'field'")
    if "value" not in node:
        raise RuleError(f"{path}: comparison needs a 'value'")
    _validate_anchor(node, path)


def _validate_anchor(node, path) -> None:
    anchor = node.get("anchor")
    if not isinstance(anchor, dict):
        raise RuleError(f"{path}: leaf has no anchor -- an unanchored rule cannot be proven")
    for key in ("doc_sha256", "start", "end"):
        if key not in anchor:
            raise RuleError(f"{path}: anchor missing '{key}'")
    if not isinstance(anchor["start"], int) or not isinstance(anchor["end"], int):
        raise RuleError(f"{path}: anchor offsets must be integers")
    if anchor["start"] < 0 or anchor["end"] <= anchor["start"]:
        raise RuleError(f"{path}: anchor range [{anchor['start']}, {anchor['end']}) is not valid")


def _kleene_and(values):
    if FALSE in values:
        return FALSE
    return UNKNOWN if UNKNOWN in values else TRUE


def _kleene_or(values):
    if TRUE in values:
        return TRUE
    return UNKNOWN if UNKNOWN in values else FALSE


def evaluate(node, profile: dict, ev: Evaluation | None = None) -> Evaluation:
    """Pure function. No LLM, no network. Same inputs -> same verdict, always."""
    ev = ev or Evaluation(value=UNKNOWN)
    ev.value = _eval_node(node, profile, ev)
    return ev


def _eval_node(node, profile, ev) -> str:
    op = node["op"]

    if op == "and":
        return _kleene_and([_eval_node(c, profile, ev) for c in node["args"]])
    if op == "or":
        return _kleene_or([_eval_node(c, profile, ev) for c in node["args"]])
    if op == "not":
        inner = _eval_node(node["args"][0], profile, ev)
        return {TRUE: FALSE, FALSE: TRUE, UNKNOWN: UNKNOWN}[inner]

    if op == AUTHORITY_OP:
        ev.authorities.append({"authority": node["authority"], "anchor": node["anchor"]})
        return UNKNOWN

    field_name = node["field"]
    actual = profile.get(field_name)
    if actual is None:
        if field_name not in ev.unknown_fields:
            ev.unknown_fields.append(field_name)
        return UNKNOWN

    try:
        result = COMPARISONS[op](actual, node["value"])
    except TypeError:
        # e.g. comparing str to int -- unprovable, not false
        if field_name not in ev.unknown_fields:
            ev.unknown_fields.append(field_name)
        return UNKNOWN

    ev.fired.append({"field": field_name, "op": op, "value": node["value"],
                     "actual": actual, "result": result, "anchor": node["anchor"]})
    return TRUE if result else FALSE


def next_unknown_field(node, profile: dict) -> str | None:
    """The next question to ask is DERIVED from the rule, not from a hardcoded slot list."""
    ev = evaluate(node, profile)
    if ev.value != UNKNOWN:
        return None
    return ev.unknown_fields[0] if ev.unknown_fields else None
