"""Tests for the local, no-network helpers."""
from briefcheck.cite import (
    brief_case_name, nearby_quote, names_match, quote_appears,
    has_negative_treatment, clean_case_name,
)


def test_brief_case_name_before_citation():
    text = "As the Court explained in Bell Atlantic Corp. v. Twombly, 550 U.S. 544 (2007)."
    start = text.index("550 U.S. 544")
    name = brief_case_name(text, start)
    assert name is not None and "Twombly" in name


def test_brief_case_name_strips_signal():
    text = "See Ashcroft v. Iqbal, 556 U.S. 662 (2009)."
    start = text.index("556 U.S. 662")
    assert brief_case_name(text, start) == "Ashcroft v. Iqbal"


def test_nearby_quote_picks_longest():
    text = 'The court held that a plaintiff must plead "enough facts to state a claim to relief that is plausible on its face," 550 U.S. 544.'
    start = text.index("550 U.S. 544")
    q = nearby_quote(text, start)
    assert q is not None and "plausible on its face" in q


def test_nearby_quote_none_when_absent():
    text = "Defendant cites 410 U.S. 113 without any quotation."
    start = text.index("410 U.S. 113")
    assert nearby_quote(text, start) is None


def test_names_match_true_false_none():
    assert names_match("Bell Atlantic Corp. v. Twombly", ["Bell Atlantic Corp. v. Twombly"]) is True
    assert names_match("Doe v. Wrongname", ["Brown v. Board of Education"]) is False
    assert names_match(None, ["Anything"]) is None
    assert names_match("Some v. Case", []) is None


def test_quote_appears_normalizes_whitespace():
    opinion = "We hold that\nenough   facts to state a claim is required."
    assert quote_appears("enough facts to state a claim", opinion) is True
    assert quote_appears("never written in the opinion", opinion) is False


def test_has_negative_treatment():
    assert "overruled" in has_negative_treatment("This decision was later overruled by the Court.")
    assert has_negative_treatment("A neutral citing sentence.") == []


def test_clean_case_name():
    assert clean_case_name("see  Roe v. Wade") == "Roe v. Wade"
