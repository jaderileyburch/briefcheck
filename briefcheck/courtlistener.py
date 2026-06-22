"""CourtListener v4 client for BriefCheck.

Bring-your-own-credential: set COURTLISTENER_TOKEN. Talks only to the public
CourtListener API. Federal and state appellate case law as held in CourtListener;
coverage is large but not exhaustive, which matters for how a "not found" result
should be read (a flag to verify, not proof of fabrication).

Reference: https://www.courtlistener.com/help/api/rest/citation-lookup/
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests

API_BASE = "https://www.courtlistener.com/api/rest/v4"
CITATION_LOOKUP = f"{API_BASE}/citation-lookup/"
OPINIONS = f"{API_BASE}/opinions/"
OPINIONS_CITED = f"{API_BASE}/opinions-cited/"

TOKEN_ENV = "COURTLISTENER_TOKEN"
MAX_CHARS = 60000          # API hard limit is 64,000; stay under it.
MAX_CITES_PER_REQUEST = 250
REQUEST_TIMEOUT = 120
SLEEP = 0.4


class AuthError(RuntimeError):
    pass


def get_token() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise AuthError(
            f"No CourtListener token. Set {TOKEN_ENV} to your token from "
            f"https://www.courtlistener.com/profile/"
        )
    return token


def _opinion_id_from_url(url: str) -> int | None:
    parts = [p for p in str(url).rstrip("/").split("/") if p]
    if parts and parts[-1].isdigit():
        return int(parts[-1])
    return None


class CourtListenerClient:
    """Thin client. Methods used by the checker are kept small so a fake can
    stand in for them during testing."""

    def __init__(self, token: str | None = None):
        self.token = token or get_token()
        self.headers = {"Authorization": f"Token {self.token}", "Accept": "application/json"}

    def _get(self, url: str, params: dict | None = None) -> dict:
        resp = requests.get(url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 401:
            raise AuthError("CourtListener rejected the token (HTTP 401).")
        resp.raise_for_status()
        return resp.json()

    def lookup_citations(self, text: str) -> list[dict[str, Any]]:
        """POST brief text to the citation-lookup API, chunked to fit limits.

        Returns the API's per-citation result dicts, with start_index/end_index
        adjusted back to offsets in the full text.
        """
        results: list[dict[str, Any]] = []
        for base in range(0, len(text), MAX_CHARS):
            chunk = text[base:base + MAX_CHARS]
            resp = requests.post(
                CITATION_LOOKUP,
                headers=self.headers,
                data={"text": chunk},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 401:
                raise AuthError("CourtListener rejected the token (HTTP 401).")
            resp.raise_for_status()
            for item in resp.json() or []:
                if isinstance(item.get("start_index"), int):
                    item["start_index"] += base
                if isinstance(item.get("end_index"), int):
                    item["end_index"] += base
                results.append(item)
            time.sleep(SLEEP)
        return results

    def opinion_text_from_cluster(self, cluster: dict[str, Any]) -> str | None:
        """Fetch the lead opinion's plain text for a cluster returned by lookup."""
        sub = cluster.get("sub_opinions") or []
        opinion_id = None
        if sub:
            opinion_id = _opinion_id_from_url(sub[0])
        if opinion_id is None and cluster.get("id"):
            data = self._get(OPINIONS, {"cluster": cluster["id"]})
            res = data.get("results") or []
            if res:
                opinion_id = res[0].get("id")
        if opinion_id is None:
            return None
        return self.get_opinion_text(opinion_id)

    def get_opinion_text(self, opinion_id: int) -> str | None:
        data = self._get(f"{OPINIONS}{opinion_id}/")
        return data.get("plain_text") or data.get("html_with_citations") or None

    def citing_opinion_ids(self, cited_opinion_id: int, cap: int = 25) -> list[int]:
        """Forward citations: later opinions that cite the given opinion."""
        ids: list[int] = []
        data = self._get(OPINIONS_CITED, {"cited_opinion": cited_opinion_id})
        while True:
            for row in data.get("results", []) or []:
                oid = _opinion_id_from_url(row.get("citing_opinion", ""))
                if oid:
                    ids.append(oid)
                if len(ids) >= cap:
                    return ids
            nxt = data.get("next")
            if not nxt:
                return ids
            data = self._get(nxt)
            time.sleep(SLEEP)
