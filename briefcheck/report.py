"""Standalone HTML authority-audit report."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Template

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>BriefCheck :: Authority Audit</title>
<style>
:root { color-scheme: light; --bg:#fff; --surface:#f7f7f5; --border:#d9d9d4; --text:#1a1a1a; --muted:#5c5c5c;
  --accent:#7a1f4f; --ok:#1f7a4d; --ok-bg:#e9f7f0; --flag:#b3261e; --flag-bg:#fdecec; --flag-border:#e3a9a9;
  --amber:#9a6a00; --amber-bg:#fff8e7; --amber-border:#e6d58a; }
* { box-sizing:border-box; }
body { margin:0; font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); line-height:1.5; }
.container { max-width:1000px; margin:0 auto; padding:40px 24px 80px; }
h1 { font-size:25px; margin:0 0 4px; font-weight:700; }
.subtitle { color:var(--muted); font-size:14px; margin:0 0 6px; }
.meta { color:var(--muted); font-size:13px; margin-bottom:8px; }
h2 { font-size:18px; margin:30px 0 10px; padding-bottom:6px; border-bottom:1px solid var(--border); }
.banner { border-radius:8px; padding:16px 18px; margin:18px 0; font-size:15px; }
.banner.bad { background:var(--flag-bg); border:1px solid var(--flag-border); }
.banner.clean { background:var(--ok-bg); border:1px solid #a9d9c0; }
.banner .big { font-size:18px; font-weight:700; }
.counts { display:flex; flex-wrap:wrap; gap:10px; margin:14px 0; }
.chip { background:var(--surface); border:1px solid var(--border); border-radius:18px; padding:5px 13px; font-size:13px; }
.chip.flag { background:var(--flag-bg); border-color:var(--flag-border); color:var(--flag); font-weight:600; }
.cite { border:1px solid var(--border); border-radius:7px; padding:13px 15px; margin:11px 0; }
.cite.flagged { background:var(--flag-bg); border-color:var(--flag-border); }
.priority { border:2px solid var(--flag-border); background:var(--flag-bg); border-radius:8px; padding:16px 18px; margin:20px 0; }
.priority h2 { margin:0 0 4px; border:none; padding:0; color:var(--flag); font-size:18px; }
.priority .lead { font-size:13.5px; color:#5a1a16; margin:0 0 12px; }
.priority .mm { background:var(--bg); border:1px solid var(--flag-border); border-radius:6px; padding:10px 12px; margin:8px 0; }
.priority .mm .c { font-family:ui-monospace,Menlo,monospace; font-size:14px; font-weight:600; }
.priority .mm .pair { font-size:13.5px; margin-top:4px; }
.priority .mm .pair .b { color:var(--muted); } .priority .mm .pair .r { color:var(--flag); font-weight:600; }
.cite .row1 { display:flex; justify-content:space-between; align-items:baseline; gap:12px; }
.cite .c { font-family:ui-monospace,Menlo,monospace; font-size:14px; font-weight:600; }
.cite .name { color:var(--muted); font-size:13px; margin-top:2px; }
.badge { font-size:11px; text-transform:uppercase; letter-spacing:.05em; padding:3px 9px; border-radius:11px; white-space:nowrap; font-weight:700; }
.badge.ok { background:var(--ok-bg); color:var(--ok); }
.badge.bad { background:#fff; color:var(--flag); border:1px solid var(--flag-border); }
.badge.amber { background:var(--amber-bg); color:var(--amber); border:1px solid var(--amber-border); }
.checks { margin-top:9px; display:flex; flex-direction:column; gap:4px; }
.check { font-size:13px; }
.check .k { color:var(--muted); display:inline-block; min-width:150px; }
.check .pass { color:var(--ok); } .check .fail { color:var(--flag); font-weight:600; } .check .na { color:var(--muted); }
.flags { margin-top:8px; }
.flags li { color:var(--flag); font-size:13px; }
.quote { font-style:italic; color:var(--muted); font-size:12.5px; margin-top:4px; }
.note-box { background:var(--amber-bg); border:1px solid var(--amber-border); border-radius:6px; padding:12px 14px; margin:22px 0; font-size:13px; }
.footnote { margin-top:36px; padding-top:16px; border-top:1px solid var(--border); font-size:12px; color:var(--muted); }
</style></head><body><div class="container">

<h1>BriefCheck</h1>
<p class="subtitle">Authority Audit :: source <code>{{ source }}</code></p>
<div class="meta">Generated {{ generated_at }}</div>

{% set s = summary %}
{% set problems = s.not_found + s.name_mismatch + s.quote_failures %}
{% if problems > 0 %}
<div class="banner bad">
  <div class="big">{{ problems }} citation issue{{ 's' if problems != 1 else '' }} to verify</div>
  Review the flagged authorities below. A "not found" result is a lead to verify, not proof of fabrication, but it is where opposing counsel's hallucinated or miscited authority shows up.
</div>
{% else %}
<div class="banner clean">
  <div class="big">No citation issues flagged</div>
  Every citation resolved in CourtListener and no name or quote mismatch was detected. Coverage is not exhaustive, so still confirm anything unusual by hand.
</div>
{% endif %}

<div class="counts">
  <span class="chip">{{ s.total }} citations parsed</span>
  <span class="chip">{{ s.found }} found</span>
  {% if s.not_found %}<span class="chip flag">{{ s.not_found }} not found</span>{% endif %}
  {% if s.ambiguous %}<span class="chip">{{ s.ambiguous }} ambiguous</span>{% endif %}
  {% if s.name_mismatch %}<span class="chip flag">{{ s.name_mismatch }} name mismatch</span>{% endif %}
  {% if s.quote_failures %}<span class="chip flag">{{ s.quote_failures }} quote not verified</span>{% endif %}
  {% if treatment and s.treatment_flags %}<span class="chip flag">{{ s.treatment_flags }} treatment flags</span>{% endif %}
</div>

{% if name_mismatches %}
<div class="priority">
  <h2>Citation correct, case name wrong</h2>
  <p class="lead">These citations resolve to a real decision, but the case name in the brief does not match the case at that reporter and page. A right citation with the wrong name is a classic fabrication signature. Look here first.</p>
  {% for r in name_mismatches %}
  <div class="mm">
    <span class="c">{{ r.citation }}</span>
    <div class="pair"><span class="b">brief: {{ r.brief_case_name }}</span> &nbsp;resolves to&nbsp; <span class="r">{{ r.resolved_case_name }}</span></div>
  </div>
  {% endfor %}
</div>
{% endif %}

<h2>Citations</h2>
{% for r in results %}
<div class="cite {{ 'flagged' if r.flags else '' }}">
  <div class="row1">
    <div>
      <span class="c">{{ r.citation }}</span>
      {% if r.brief_case_name %}<div class="name">brief: {{ r.brief_case_name }}{% if r.resolved_case_name and r.name_match is sameas false %} :: resolved: {{ r.resolved_case_name }}{% endif %}</div>{% endif %}
    </div>
    {% if r.status == 'exists' %}<span class="badge ok">Exists</span>
    {% elif r.status == 'ambiguous' %}<span class="badge amber">Ambiguous</span>
    {% else %}<span class="badge bad">Not found</span>{% endif %}
  </div>
  <div class="checks">
    <div class="check"><span class="k">Case exists</span>
      {% if r.exists %}<span class="pass">yes</span>{% elif r.status == 'ambiguous' %}<span class="na">multiple matches</span>{% else %}<span class="fail">not found in CourtListener</span>{% endif %}
    </div>
    <div class="check"><span class="k">Name matches citation</span>
      {% if r.name_match is sameas true %}<span class="pass">yes</span>{% elif r.name_match is sameas false %}<span class="fail">no, name does not match</span>{% else %}<span class="na">not compared</span>{% endif %}
    </div>
    <div class="check"><span class="k">Quoted holding verified</span>
      {% if r.quote_verified is sameas true %}<span class="pass">yes, quote appears in opinion</span>{% elif r.quote_verified is sameas false %}<span class="fail">no, quote not found in opinion</span>{% else %}<span class="na">no quote checked</span>{% endif %}
    </div>
    {% if treatment %}
    <div class="check"><span class="k">Treatment screen</span>
      {% if r.treatment and r.treatment.negative_terms %}<span class="fail">negative language found: {{ r.treatment.negative_terms|join(', ') }}</span>
      {% elif r.treatment %}<span class="na">{{ r.treatment.citing_count }} citing opinions, no negative language</span>
      {% else %}<span class="na">not screened</span>{% endif %}
    </div>
    {% endif %}
  </div>
  {% if r.quote %}<div class="quote">quoted: "{{ r.quote[:200] }}{{ '...' if r.quote|length > 200 else '' }}"</div>{% endif %}
  {% if r.flags %}<ul class="flags">{% for f in r.flags %}<li>{{ f }}</li>{% endfor %}</ul>{% endif %}
</div>
{% endfor %}

<div class="note-box">
<strong>How to read this, and what it is not.</strong> BriefCheck verifies citations against CourtListener, whose coverage of federal and state case law is large but not complete. A <em>not found</em> result means the citation did not resolve there: it is a strong lead to verify, not proof the case is invented. Quote verification confirms whether a quoted passage literally appears in the cited opinion; it does not judge whether the holding is characterized fairly. The treatment screen looks for negative-treatment words in later opinions and is <strong>not</strong> a substitute for Shepard's or KeyCite. This is not legal advice. Confirm every flag against the primary source before relying on it.
</div>

<div class="footnote">Source: CourtListener Citation Lookup API. Generated by BriefCheck. Designed by PinkViper Labs.</div>

</div></body></html>
"""


def generate_report(audit: dict[str, Any], source: str, out_path: Path) -> None:
    name_mismatches = [r for r in audit["results"] if r.get("name_match") is False]
    html = Template(REPORT_TEMPLATE).render(
        generated_at=datetime.now(timezone.utc).isoformat(),
        source=source,
        results=audit["results"],
        summary=audit["summary"],
        treatment=audit.get("treatment", False),
        name_mismatches=name_mismatches,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
