"""Local text helpers, no network.

Given the brief text and the character offset of a citation (from the lookup
API), pull the case name the brief used and any quoted passage attributed to
that citation, and compare names.
"""
from __future__ import annotations

import re

# Case name immediately preceding a citation: "X v. Y" possibly with a signal.
_CASENAME_RE = re.compile(
    r"([A-Z][A-Za-z.&'\-]*(?:\s+[A-Za-z.&'\-]+){0,6}?\s+v\.?\s+[A-Z][A-Za-z.&'\-]*(?:\s+[A-Za-z.&'\-]+){0,6}?),?\s*$"
)
_SIGNAL_RE = re.compile(
    r"^(?:see also|see,?\s*e\.g\.,?|see|accord|cf\.?|e\.g\.,?|citing|quoting|but see|compare|contra|in)\s+",
    re.I,
)

# Quotation marks: straight and curly.
_QUOTE_RE = re.compile(r"[\"\u201c]([^\"\u201c\u201d]{12,}?)[\"\u201d]")

# Negative-treatment language used only as a screening signal.
NEGATIVE_TREATMENT_TERMS = [
    "overruled", "overruling", "abrogated", "abrogating", "superseded",
    "no longer good law", "reversed", "vacated", "is not good law",
    "has been overruled", "we overrule", "disapproved",
]
_NEG_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in NEGATIVE_TREATMENT_TERMS) + r")\b", re.I)


def clean_case_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    return _SIGNAL_RE.sub("", name).strip()


def brief_case_name(text: str, citation_start: int, window: int = 90) -> str | None:
    """The 'X v. Y' the brief placed just before the citation, if any."""
    prefix = text[max(0, citation_start - window):citation_start]
    m = _CASENAME_RE.search(prefix)
    if not m:
        return None
    name = clean_case_name(m.group(1))
    return name or None


def nearby_quote(text: str, citation_start: int, window: int = 400, lower_bound: int = 0) -> str | None:
    """The longest quoted passage between the previous citation and this one.

    lower_bound is the end offset of the preceding citation, so a quote is
    attributed only to the first citation that follows it, never bled onto a
    later citation hundreds of characters away.
    """
    seg_start = max(lower_bound, citation_start - window)
    if seg_start >= citation_start:
        return None
    segment = text[seg_start:citation_start]
    quotes = [m.group(1).strip().strip('.,;:"\u201c\u201d ') for m in _QUOTE_RE.finditer(segment)]
    quotes = [q for q in quotes if len(q) >= 12]
    if not quotes:
        return None
    return max(quotes, key=len)


def _name_tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z]+", name.lower()) if len(t) > 2 and t != "the"}


def names_match(brief_name: str | None, resolved_names: list[str]) -> bool | None:
    """Loose match: do the brief's party tokens overlap a resolved case name?

    Returns True/False, or None when there is nothing to compare.
    """
    if not brief_name or not resolved_names:
        return None
    bt = _name_tokens(brief_name)
    if not bt:
        return None
    for rn in resolved_names:
        rt = _name_tokens(rn)
        if not rt:
            continue
        overlap = len(bt & rt)
        if overlap >= 1 and overlap >= min(2, len(bt)):
            return True
    return False


def quote_appears(quote: str, opinion_text: str | None) -> bool:
    """Does the quoted passage actually appear in the opinion (whitespace-normalized)?"""
    if not quote or not opinion_text:
        return False
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    return norm(quote) in norm(opinion_text)


def has_negative_treatment(text: str | None) -> list[str]:
    if not text:
        return []
    return sorted({m.group(1).lower() for m in _NEG_RE.finditer(text)})
