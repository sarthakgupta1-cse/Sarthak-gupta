"""Command line entry point."""

from __future__ import annotations

import asyncio
import logging
from typing import ClassVar

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .compliance import suppress
from .config import load_settings
from .models import EmailStatus
from .pipeline import Pipeline
from .sinks import SINKS

app = typer.Typer(
    add_completion=False,
    help="Find SaaS founders and enrich them with contact data.",
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


@app.command()
def run(
    limit: int = typer.Option(50, help="Max leads to collect per discovery source."),
    domains: str | None = typer.Option(
        None, help="Comma-separated company domains to crawl for founders."
    ),
    sink: str | None = typer.Option(
        None, help=f"Override the output sink. One of: {', '.join(SINKS)}."
    ),
    config: str = typer.Option("config.yaml", help="Path to the config file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Collect but write nothing."),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
) -> None:
    """Run one full discovery + enrichment pass."""
    _setup_logging(verbose)
    settings = load_settings(config)
    domain_list = [d.strip() for d in domains.split(",") if d.strip()] if domains else None

    report = asyncio.run(
        Pipeline(settings).run(
            limit=limit, domains=domain_list, dry_run=dry_run, sink_name=sink
        )
    )
    _print_report(report, dry_run)


@app.command()
def crawl(
    domains: str = typer.Argument(..., help="Comma-separated domains, e.g. acme.io,beta.com"),
    sink: str | None = typer.Option(None),
    config: str = typer.Option("config.yaml"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
) -> None:
    """Find the founders at a known list of companies."""
    _setup_logging(verbose)
    settings = load_settings(config)
    # Company-site crawl only; the open-web sources would ignore our domain list.
    for name in ("hackernews", "producthunt", "github"):
        settings.discovery.setdefault(name, {})
        if isinstance(settings.discovery[name], dict):
            settings.discovery[name]["enabled"] = False

    domain_list = [d.strip() for d in domains.split(",") if d.strip()]
    report = asyncio.run(
        Pipeline(settings).run(
            limit=len(domain_list), domains=domain_list, dry_run=dry_run, sink_name=sink
        )
    )
    _print_report(report, dry_run)


@app.command()
def optout(
    entry: str = typer.Argument(..., help="Email, domain or LinkedIn slug to suppress."),
) -> None:
    """Record an opt-out so this person is never written or contacted again."""
    suppress(entry)
    console.print(f"[green]Suppressed[/green] {entry} — excluded from all future runs.")


@app.command()
def doctor(config: str = typer.Option("config.yaml")) -> None:
    """Show which sources, enrichers and sinks are actually usable right now."""
    from .discovery import ALL_SOURCES
    from .enrich import ALL_ENRICHERS

    settings = load_settings(config)
    table = Table(title="founder-agent readiness", header_style="bold")
    for column in ("Component", "Kind", "Status", "Detail"):
        table.add_column(column)

    class _Stub:
        """availability checks never touch the network, so a stub client is enough."""

        stats: ClassVar[dict] = {}

    for cls in ALL_SOURCES:
        ok, why = cls(settings, _Stub()).available()
        table.add_row(cls.name, "discovery",
                      "[green]ready[/green]" if ok else "[yellow]skipped[/yellow]", why or "-")
    for cls in ALL_ENRICHERS:
        ok, why = cls(settings, _Stub()).available()
        table.add_row(cls.name, "enrichment",
                      "[green]ready[/green]" if ok else "[yellow]skipped[/yellow]", why or "-")
    for name, cls in SINKS.items():
        ok, why = cls(settings).available()
        marker = " (default)" if name == settings.output.get("sink") else ""
        table.add_row(name + marker, "sink",
                      "[green]ready[/green]" if ok else "[yellow]unavailable[/yellow]", why or "-")

    console.print(table)
    console.print(
        "\n[dim]Sources marked 'skipped' for a missing key still let the run proceed; "
        "the agent uses whatever is configured.[/dim]"
    )


def _print_report(report, dry_run: bool) -> None:
    table = Table(title="Top leads", header_style="bold")
    for col in ("Score", "Name", "Role", "Company", "Email", "Status", "LinkedIn", "TG"):
        table.add_column(col, overflow="ellipsis")

    for lead in report.leads[:25]:
        status_colour = {
            EmailStatus.VERIFIED: "green",
            EmailStatus.PUBLISHED: "cyan",
            EmailStatus.GUESSED: "yellow",
            EmailStatus.RISKY: "magenta",
        }.get(lead.email_status, "dim")
        table.add_row(
            str(lead.score),
            (lead.full_name or "-")[:24],
            (lead.role or "-")[:20],
            (lead.company or "-")[:20],
            (lead.email or "-")[:30],
            f"[{status_colour}]{lead.email_status}[/{status_colour}]",
            "yes" if lead.linkedin_url else "-",
            lead.telegram_handle or "-",
        )
    console.print(table)

    summary = Table.grid(padding=(0, 2))
    summary.add_row("discovered", str(report.discovered))
    summary.add_row("after dedupe", str(report.after_dedupe))
    summary.add_row("enriched", str(report.enriched))
    summary.add_row("suppressed (opt-out)", str(report.suppressed))
    summary.add_row("below score threshold", str(report.below_threshold))
    summary.add_row("[bold]contactable[/bold]", f"[bold]{report.contactable}[/bold]")
    summary.add_row("written", "0 (dry run)" if dry_run else str(report.written))
    summary.add_row("estimated API cost", f"${report.estimated_cost_usd:.2f}")
    summary.add_row("http", str(report.http))
    console.print(summary)

    if report.skipped:
        console.print("\n[yellow]Skipped components:[/yellow]")
        for name, why in report.skipped.items():
            console.print(f"  [dim]{name}:[/dim] {why}")

    console.print(
        "\n[dim]Only rows with status 'verified' or 'published' should receive cold "
        "outreach. Run [/dim][bold]founder-agent optout <email>[/bold][dim] on any removal "
        "request.[/dim]"
    )


if __name__ == "__main__":
    app()
