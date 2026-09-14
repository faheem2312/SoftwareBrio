"""
Autonomous Lead Enrichment Agent - CLI Entrypoint
"""

import argparse
import sys
from typing import List

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from schema import CompanyProfile, TeamMember

console = Console(force_terminal=True)

DEFAULT_DOMAINS = ["postman.com", "supabase.com", "vapi.ai"]


def process_domain_stub(domain: str) -> CompanyProfile:
    """
    Milestone 1 Stub: Simulates domain enrichment pipeline.
    In Milestone 2-4, this orchestrates crawler, cleaner, and LLM extractor.
    """
    console.print(f"[bold cyan]>> Processing domain:[/bold cyan] [underline]{domain}[/underline]")
    console.print(f"  [dim]• Discovering subpages for {domain}... (stub)[/dim]")
    console.print(f"  [dim]• Cleaning & optimizing tokens... (stub)[/dim]")
    console.print(f"  [dim]• Extracting structured intelligence via Gemini... (stub)[/dim]")

    # Return a validated skeleton CompanyProfile
    return CompanyProfile(
        domain=domain,
        company_overview=f"{domain.capitalize()} is a technology company providing modern platform infrastructure. The platform enables developers to build and scale modern software efficiently.",
        target_audience="Software engineers and development teams building modern applications.",
        contact_emails=[f"info@{domain}"],
        team_members=[
            TeamMember(name="Leadership Team", role="Executive", linkedin_url="")
        ],
        confidence_score=0.75,
        pages_scraped=[f"https://{domain}", f"https://{domain}/about"],
        tokens_used=1250,
        estimated_cost_usd=0.00018,
    )


def display_summary_table(profiles: List[CompanyProfile]):
    """Displays a formatted Rich table summarizing the results."""
    table = Table(title="[bold green]Lead Enrichment Results (Milestone 1 Skeleton)[/bold green]")
    table.add_column("Domain", style="cyan", no_wrap=True)
    table.add_column("Overview (2 Sentences)", style="white")
    table.add_column("Target Audience (ICP)", style="yellow")
    table.add_column("Emails", style="magenta")
    table.add_column("Key Team", style="blue")
    table.add_column("Confidence", style="green", justify="right")

    for profile in profiles:
        emails = ", ".join(profile.contact_emails) if profile.contact_emails else "None"
        team = ", ".join(f"{m.name} ({m.role})" for m in profile.team_members) if profile.team_members else "None"
        table.add_row(
            profile.domain,
            profile.company_overview,
            profile.target_audience,
            emails,
            team,
            f"{profile.confidence_score:.2f}",
        )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Lead Enrichment Agent CLI"
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        default=DEFAULT_DOMAINS,
        help="List of domains to enrich (e.g. --domains postman.com supabase.com vapi.ai)",
    )
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold white]Autonomous Lead Enrichment Agent[/bold white]\n"
            "[cyan]Targeting:[/cyan] " + ", ".join(args.domains),
            border_style="blue",
        )
    )

    results = []
    for domain in args.domains:
        profile = process_domain_stub(domain.strip())
        results.append(profile)
        console.print(f"[bold green]✓ Completed skeleton run for {domain}[/bold green]\n")

    display_summary_table(results)


if __name__ == "__main__":
    main()
