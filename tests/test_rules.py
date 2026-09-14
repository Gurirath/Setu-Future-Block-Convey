import pytest
from setu.rules import (validate, evaluate, next_unknown_field, RuleError,
                        TRUE, FALSE, UNKNOWN)

A = {"doc_sha256": "deadbeef", "start": 10, "end": 40}

def leaf(op, fieldname, value, anchor=A):
    return {"op": op, "field": fieldname, "value": value, "anchor": anchor}

RULE = {"op": "and", "args": [
    leaf("gte", "age", 60),
    leaf("eq", "is_bpl", True),
    {"op": "not", "args": [leaf("eq", "has_other_pension", True)]},
]}

def test_all_satisfied_is_eligible():
    ev = evaluate(RULE, {"age": 70, "is_bpl": True, "has_other_pension": False})
    assert ev.value == TRUE

def test_missing_data_is_unknown_never_false():
    # age known & passing, but BPL unknown -> must NOT say "not eligible"
    ev = evaluate(RULE, {"age": 70})
    assert ev.value == UNKNOWN
    assert "is_bpl" in ev.unknown_fields

def test_definite_failure_wins_over_unknown():
    # age fails outright; remaining unknowns cannot rescue it
    ev = evaluate(RULE, {"age": 45})
    assert ev.value == FALSE

def test_or_short_circuits_to_true_with_unknowns():
    rule = {"op": "or", "args": [leaf("eq", "is_bpl", True), leaf("gte", "age", 60)]}
    assert evaluate(rule, {"is_bpl": True}).value == TRUE

def test_not_propagates_unknown():
    rule = {"op": "not", "args": [leaf("eq", "x", 1)]}
    assert evaluate(rule, {}).value == UNKNOWN

def test_type_mismatch_is_unknown_not_crash():
    ev = evaluate(leaf("gte", "age", 60), {"age": "sixty"})
    assert ev.value == UNKNOWN and "age" in ev.unknown_fields

def test_fired_leaf_carries_its_anchor():
    ev = evaluate(RULE, {"age": 70, "is_bpl": True, "has_other_pension": False})
    assert all(f["anchor"] == A for f in ev.fired)
    assert any(f["field"] == "age" for f in ev.fired)

def test_authority_op_yields_unknown_and_records_authority():
    rule = {"op": "requires_authority", "authority": "SECC-2011 beneficiary database",
            "anchor": A}
    ev = evaluate(rule, {"age": 70})
    assert ev.value == UNKNOWN
    assert ev.authorities[0]["authority"].startswith("SECC")

def test_next_question_is_derived_from_rule():
    assert next_unknown_field(RULE, {"age": 70}) == "is_bpl"
    assert next_unknown_field(RULE, {}) == "age"
    assert next_unknown_field(RULE, {"age": 70, "is_bpl": True,
                                     "has_other_pension": False}) is None

def test_determinism():
    profile = {"age": 70, "is_bpl": True, "has_other_pension": False}
    assert len({evaluate(RULE, profile).value for _ in range(50)}) == 1

@pytest.mark.parametrize("bad,msg", [
    ({"op": "gte", "field": "age", "value": 60}, "anchor"),
    ({"op": "gte", "value": 60, "anchor": A}, "field"),
    ({"op": "frobnicate", "field": "age", "value": 1, "anchor": A}, "unknown op"),
    ({"op": "and", "args": []}, "non-empty"),
    ({"op": "not", "args": [leaf("eq","a",1), leaf("eq","b",2)]}, "exactly one"),
    ({"op": "requires_authority", "anchor": A}, "authority"),
    ({"op": "gte", "field": "age", "value": 60,
      "anchor": {"doc_sha256":"x","start":40,"end":10}}, "not valid"),
])
def test_validation_fails_closed(bad, msg):
    with pytest.raises(RuleError) as e:
        validate(bad)
    assert msg in str(e.value)

def test_validate_accepts_wellformed_rule():
    validate(RULE)
