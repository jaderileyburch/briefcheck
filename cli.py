"""Command line interface for BriefCheck.

Audit the authorities in an opposing brief: does each case exist, is the quoted
holding actually in the opinion, and is there negative treatment. Built on the
CourtListener Citation Lookup API. Bring your own token (COURTLISTENER_TOKEN).
Not legal advice. Designed by PinkViper Labs.
"""
from __future__ import annotations

from pathlib import Path

import click

from briefcheck import check as check_mod
from briefcheck import extract as extract_mod
from briefcheck import report as report_mod
from briefcheck.courtlistener import AuthError, CourtListenerClient

DEFAULT_OUT_DIR = "out"


@click.group()
def cli() -> None:
    """BriefCheck: audit the citations in an opposing brief.

    Set COURTLISTENER_TOKEN to your token from courtlistener.com/profile.
    Not legal advice. Designed by PinkViper Labs.
    """


def _run(complaint_path, treatment, no_quotes):
    text = extract_mod.extract_text(complaint_path)
    client = CourtListenerClient()
    return check_mod.check_brief(
        text, client,
        verify_quotes=not no_quotes,
        treatment=treatment,
    )


@cli.command()
@click.argument("brief", type=click.Path(exists=True))
@click.option("--treatment", is_flag=True, default=False, help="Also screen later opinions for negative treatment (slower, opt-in).")
@click.option("--no-quotes", is_flag=True, default=False, help="Skip quoted-passage verification.")
@click.pass_context
def check(ctx, brief, treatment, no_quotes):
    """Audit a brief and print the citation summary."""
    try:
        audit = _run(brief, treatment, no_quotes)
    except AuthError as e:
        raise click.ClickException(str(e))
    except (FileNotFoundError, RuntimeError) as e:
        raise click.ClickException(str(e))

    s = audit["summary"]
    click.echo(f"\nBriefCheck :: {brief}")
    click.echo(f"\n{s['total']} citations parsed :: {s['found']} found :: "
               f"{s['not_found']} not found :: {s['ambiguous']} ambiguous")
    if s["name_mismatch"]:
        click.echo(f"  {s['name_mismatch']} name mismatch")
    if s["quote_failures"]:
        click.echo(f"  {s['quote_failures']} quoted passages not verified")
    if audit["treatment"] and s["treatment_flags"]:
        click.echo(f"  {s['treatment_flags']} negative-treatment flags")

    flagged = [r for r in audit["results"] if r["flags"]]
    if flagged:
        click.echo("\nFlagged citations to verify:")
        for r in flagged:
            name = f" ({r['brief_case_name']})" if r["brief_case_name"] else ""
            click.echo(f"  - {r['citation']}{name}")
            for f in r["flags"]:
                click.echo(f"      {f}")
    else:
        click.echo("\nNo citation issues flagged.")

    click.echo("\nNot legal advice. A 'not found' result is a lead to verify, not proof of fabrication. "
               "Confirm every flag against the primary source.")


@cli.command()
@click.argument("brief", type=click.Path(exists=True))
@click.option("--treatment", is_flag=True, default=False, help="Also screen later opinions for negative treatment (slower, opt-in).")
@click.option("--no-quotes", is_flag=True, default=False, help="Skip quoted-passage verification.")
@click.option("--out", default=None, help="Output HTML path (default: out/briefcheck.html).")
@click.pass_context
def report(ctx, brief, treatment, no_quotes, out):
    """Write an HTML authority-audit report."""
    try:
        audit = _run(brief, treatment, no_quotes)
    except AuthError as e:
        raise click.ClickException(str(e))
    except (FileNotFoundError, RuntimeError) as e:
        raise click.ClickException(str(e))
    out_path = Path(out) if out else Path(DEFAULT_OUT_DIR) / "briefcheck.html"
    report_mod.generate_report(audit, str(brief), out_path)
    click.echo(f"Wrote: {out_path}")


if __name__ == "__main__":
    cli()
