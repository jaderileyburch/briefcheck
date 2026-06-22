"""The three checks, wired together.

Given a brief's text and a CourtListener client, for each citation:

  1. Exists      -- from the lookup status (200 found, 404/400 not found,
                    300 ambiguous), plus a name-mismatch comparison against the
                    resolved case name.
  2. Quote       -- if the brief quotes language at the citation, fetch the
                    opinion and verify the passage actually appears in it.
  3. Treatment   -- optional screen: pull later opinions that cite this case and
                    flag negative-treatment language. A screen, not a citator.

The client is injected so the orchestration can be tested without a network.
"""
from __future__ import annotations

from typing import Any, Protocol

from . import cite


class Client(Protocol):
    def lookup_citations(self, text: str) -> list[dict[str, Any]]: ...
    def opinion_text_from_cluster(self, cluster: dict[str, Any]) -> str | None: ...
    def get_opinion_text(self, opinion_id: int) -> str | None: ...
    def citing_opinion_ids(self, cited_opinion_id: int, cap: int = 25) -> list[int]: ...


STATUS_LABEL = {
    200: "exists",
    404: "not_found",
    400: "bad_reporter",
    300: "ambiguous",
    429: "not_checked",
}


def _resolved_names(clusters: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for c in clusters or []:
        n = c.get("case_name") or c.get("case_name_full") or c.get("caseName")
        if n:
            names.append(n)
    return names


def _cluster_opinion_id(cluster: dict[str, Any]) -> int | None:
    sub = cluster.get("sub_opinions") or []
    if sub:
        from .courtlistener import _opinion_id_from_url
        return _opinion_id_from_url(sub[0])
    return None


def check_brief(
    brief_text: str,
    client: Client,
    *,
    verify_quotes: bool = True,
    treatment: bool = False,
    treatment_cap: int = 25,
) -> dict[str, Any]:
    """Run the checks. Returns per-citation results plus aggregate counts."""
    lookups = client.lookup_citations(brief_text)
    # Process in document order so each quote is bounded by the prior citation.
    lookups = sorted(lookups, key=lambda it: (it.get("start_index") is None, it.get("start_index") or 0))
    results: list[dict[str, Any]] = []
    prev_end = 0

    for item in lookups:
        status_code = item.get("status")
        status = STATUS_LABEL.get(status_code, "unknown")
        start = item.get("start_index")
        end = item.get("end_index")
        clusters = item.get("clusters") or []
        resolved = _resolved_names(clusters)
        bname = cite.brief_case_name(brief_text, start) if isinstance(start, int) else None

        flags: list[str] = []
        exists = status == "exists"
        if status in ("not_found", "bad_reporter"):
            flags.append("citation not found in CourtListener")
        elif status == "ambiguous":
            flags.append("citation matches more than one decision")

        # Name mismatch (only meaningful when the case was found).
        name_match = None
        if exists:
            name_match = cite.names_match(bname, resolved)
            if name_match is False:
                flags.append("case name does not match the resolved citation")

        # Quote verification, bounded to the span since the previous citation.
        quote = cite.nearby_quote(brief_text, start, lower_bound=prev_end) if isinstance(start, int) else None
        if isinstance(end, int):
            prev_end = max(prev_end, end)
        quote_verified: bool | None = None
        if verify_quotes and exists and quote and clusters:
            opinion_text = client.opinion_text_from_cluster(clusters[0])
            quote_verified = cite.quote_appears(quote, opinion_text)
            if quote_verified is False:
                flags.append("quoted passage not found in the cited opinion")

        # Treatment screen.
        treatment_result: dict[str, Any] | None = None
        if treatment and exists and clusters:
            treatment_result = _screen_treatment(client, clusters[0], treatment_cap)
            if treatment_result and treatment_result.get("negative_terms"):
                flags.append("negative-treatment language in later opinions (verify)")

        results.append({
            "citation": item.get("citation"),
            "status": status,
            "status_code": status_code,
            "exists": exists,
            "brief_case_name": bname,
            "resolved_case_name": resolved[0] if resolved else None,
            "name_match": name_match,
            "quote": quote,
            "quote_verified": quote_verified,
            "treatment": treatment_result,
            "flags": flags,
        })

    summary = {
        "total": len(results),
        "found": sum(1 for r in results if r["exists"]),
        "not_found": sum(1 for r in results if r["status"] in ("not_found", "bad_reporter")),
        "ambiguous": sum(1 for r in results if r["status"] == "ambiguous"),
        "name_mismatch": sum(1 for r in results if r["name_match"] is False),
        "quote_failures": sum(1 for r in results if r["quote_verified"] is False),
        "treatment_flags": sum(1 for r in results if r["treatment"] and r["treatment"].get("negative_terms")),
        "flagged": sum(1 for r in results if r["flags"]),
    }
    return {"results": results, "summary": summary,
            "verify_quotes": verify_quotes, "treatment": treatment}


def _screen_treatment(client: Client, cluster: dict[str, Any], cap: int) -> dict[str, Any] | None:
    opinion_id = _cluster_opinion_id(cluster)
    if opinion_id is None:
        return None
    citing_ids = client.citing_opinion_ids(opinion_id, cap=cap)
    negative: dict[int, list[str]] = {}
    for cid in citing_ids:
        text = client.get_opinion_text(cid)
        terms = cite.has_negative_treatment(text)
        if terms:
            negative[cid] = terms
    all_terms = sorted({t for terms in negative.values() for t in terms})
    return {
        "citing_count": len(citing_ids),
        "negative_opinions": list(negative.keys()),
        "negative_terms": all_terms,
    }
