import pytest

from setu.extract import (normalize_digits, detect_script, parse_number,
                          parse_boolean, parse_value, expected_type)


@pytest.mark.parametrize("text,expected", [
    ("७०", "70"), ("௭௦", "70"), ("৭০", "70"), ("70", "70"),
])
def test_indic_digits_normalise(text, expected):
    assert normalize_digits(text) == expected


@pytest.mark.parametrize("text,lang", [
    ("I am seventy years old", "en"),
    ("मेरी उम्र सत्तर साल है", "hi"),
    ("எனக்கு எழுபது வயது", "ta"),
    ("", "en"),
    ("12345", "en"),
])
def test_script_detection(text, lang):
    assert detect_script(text) == lang


@pytest.mark.parametrize("text,value", [
    ("I am 70", 70), ("७० साल", 70), ("2 lakh", 200_000),
    ("2 लाख", 200_000), ("1.5 crore", 15_000_000),
    ("12,000 per month", 12_000), ("no number here", None),
])
def test_number_parsing_with_scale_words(text, value):
    assert parse_number(text) == value


@pytest.mark.parametrize("text,value", [
    ("yes", True), ("Yes.", True), ("haan", True), ("हां", True), ("ஆம்", True),
    ("no", False), ("nope", False), ("नहीं", False), ("இல்லை", False),
])
def test_boolean_parsing_across_languages(text, value):
    assert parse_boolean(text) is value


@pytest.mark.parametrize("text", ["maybe", "yes and no", "", "I'm not sure"])
def test_ambiguous_reply_stays_unknown(text):
    assert parse_boolean(text) is None


def test_unknown_never_becomes_false():
    """The whole point: an unparseable reply must not read as a denial."""
    assert parse_value("hmm", bool) is None
    assert parse_value("dunno", int) is None


def test_expected_type_is_inferred_from_the_rule_not_hardcoded():
    assert expected_type(True) is bool
    assert expected_type(60) is int
    assert expected_type(2.5) is float
    assert expected_type("urban") is str


def test_bool_is_not_mistaken_for_int():
    """bool is a subclass of int in Python; order of checks must handle it."""
    assert expected_type(False) is bool


def test_parse_value_routes_by_expected_type():
    assert parse_value("I am ७० years old", int) == 70
    assert parse_value("yes", bool) is True
    assert parse_value("Tamil Nadu", str) == "Tamil Nadu"
