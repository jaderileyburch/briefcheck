"""Tests for check_brief, using an offline fake CourtListener client."""
from briefcheck.check import check_brief
from briefcheck.courtlistener import _opinion_id_from_url


class FakeClient:
    """Stands in for CourtListenerClient. Locates each citation in the brief
    text to produce realistic start indices, then returns canned statuses."""

    def __init__(self, lookups, opinion_texts=None, citing=None):
        self._lookups = lookups
        self._opinion_texts = opinion_texts or {}
        self._citing = citing or {}

    def lookup_citations(self, text):
        results = []
        for L in self._lookups:
            idx = text.find(L["citation"])
            clusters = []
            if L.get("case_name"):
                oid = L.get("opinion_id", 0)
                clusters = [{
                    "case_name": L["case_name"],
                    "sub_opinions": [f"https://www.courtlistener.com/api/rest/v4/opinions/{oid}/"],
                    "id": L.get("cluster_id", 0),
                }]
            results.append({
                "citation": L["citation"],
                "status": L["status"],
                "start_index": idx,
                "end_index": idx + len(L["citation"]),
                "clusters": clusters,
            })
        return results

    def opinion_text_from_cluster(self, cluster):
        oid = _opinion_id_from_url(cluster["sub_opinions"][0])
        return self._opinion_texts.get(oid)

    def get_opinion_text(self, opinion_id):
        return self._opinion_texts.get(opinion_id)

    def citing_opinion_ids(self, cited_opinion_id, cap=25):
        return self._citing.get(cited_opinion_id, [])[:cap]


# One distinct citation per check, so each result isolates one behavior.
BRIEF = (
    'The pleading standard is settled. See Bell Atlantic Corp. v. Twombly, 550 U.S. 544 (2007). '
    'The Court required "enough facts to state a claim to relief that is plausible," 556 U.S. 662 (2009). '
    'Defendant further relies on Smith v. Fabricated, 999 U.S. 9999 (2023). '
    'It cites Doe v. Wrongname, 347 U.S. 483 (1954) for the proposition. '
    'And it quotes "a holding that was never written," 123 F.3d 456 (9th Cir. 1997).'
)

LOOKUPS = [
    # Exists, name matches, no quote attributed.
    {"citation": "550 U.S. 544", "status": 200, "case_name": "Bell Atlantic Corp. v. Twombly", "opinion_id": 101},
    # Exists, quote attributed and present in the opinion.
    {"citation": "556 U.S. 662", "status": 200, "case_name": "Ashcroft v. Iqbal", "opinion_id": 102},
    # Hallucinated: valid-looking citation, not found.
    {"citation": "999 U.S. 9999", "status": 404},
    # Exists, but the brief's case name does not match the resolved case.
    {"citation": "347 U.S. 483", "status": 200, "case_name": "Brown v. Board of Education", "opinion_id": 103},
    # Exists, but the quoted passage is not in the opinion.
    {"citation": "123 F.3d 456", "status": 200, "case_name": "Real Plaintiff v. Real Defendant", "opinion_id": 104},
]

OPINION_TEXTS = {
    101: "We address the sufficiency of the complaint under the federal rules.",
    102: "We require enough facts to state a claim to relief that is plausible on its face.",
    103: "Separate but equal has no place in public education.",
    104: "This opinion contains entirely different language than what was quoted.",
}


def _audit(**kw):
    return check_brief(BRIEF, FakeClient(LOOKUPS, OPINION_TEXTS), **kw)


def test_existence_detection():
    by = {r["citation"]: r for r in _audit()["results"]}
    assert by["550 U.S. 544"]["exists"] is True
    assert by["999 U.S. 9999"]["exists"] is False
    assert "citation not found in CourtListener" in by["999 U.S. 9999"]["flags"]


def test_name_match_and_mismatch():
    by = {r["citation"]: r for r in _audit()["results"]}
    assert by["550 U.S. 544"]["name_match"] is True
    assert by["347 U.S. 483"]["name_match"] is False
    assert any("name does not match" in f for f in by["347 U.S. 483"]["flags"])


def test_quote_verification():
    by = {r["citation"]: r for r in _audit()["results"]}
    assert by["556 U.S. 662"]["quote_verified"] is True
    assert by["123 F.3d 456"]["quote_verified"] is False
    assert any("quoted passage not found" in f for f in by["123 F.3d 456"]["flags"])


def test_summary_counts():
    s = _audit()["summary"]
    assert s["total"] == 5
    assert s["found"] == 4
    assert s["not_found"] == 1
    assert s["name_mismatch"] == 1
    assert s["quote_failures"] == 1
    assert s["flagged"] == 3


def test_no_quotes_option_skips_verification():
    by = {r["citation"]: r for r in _audit(verify_quotes=False)["results"]}
    assert by["123 F.3d 456"]["quote_verified"] is None


def test_treatment_screen():
    opinion_texts = dict(OPINION_TEXTS)
    opinion_texts[9001] = "This rule was later overruled by a subsequent decision."
    opinion_texts[9002] = "A neutral later citation."
    client = FakeClient(LOOKUPS, opinion_texts, citing={101: [9001, 9002]})
    audit = check_brief(BRIEF, client, treatment=True)
    by = {r["citation"]: r for r in audit["results"]}
    t = by["550 U.S. 544"]["treatment"]
    assert t["citing_count"] == 2
    assert "overruled" in t["negative_terms"]
    assert audit["summary"]["treatment_flags"] == 1
