"""
Autonomous Lead Enrichment Agent - CLI Entrypoint
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict, List

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
from src.crawler import WebCrawler

console = Console(force_terminal=True)

DEFAULT_DOMAINS = ["postman.com", "supabase.com", "vapi.ai"]


async def process_domain(domain: str, crawler: WebCrawler) -> CompanyProfile:
    """
    Orchestrates crawling, cleaning (Milestone 3), and LLM extraction (Milestone 4).
    """
    console.print(f"[bold cyan]>> Processing domain:[/bold cyan] [underline]{domain}[/underline]")
    
    # 1. Crawl & Subpage Discovery
    raw_pages: Dict[str, str] = await crawler.crawl_domain(domain)
    pages_scraped = list(raw_pages.keys())
    console.print(f"  [dim]• Crawled {len(pages_scraped)} pages (saved to output/scratch/{domain})[/dim]")

    # 2. Cleaning & Optimization (stubbed for Milestone 2, real in Milestone 3)
    console.print(f"  [dim]• Cleaning & optimizing tokens... (ready for Milestone 3)[/dim]")

    # 3. Extraction (stubbed for Milestone 2, real in Milestone 4)
    console.print(f"  [dim]• LLM extraction ready for Gemini API integration...[/dim]")

    total_kb = sum(len(c.encode("utf-8")) for c in raw_pages.values()) / 1024

    return CompanyProfile(
        domain=domain,
        company_overview=f"{domain.capitalize()} is a technology company providing modern platform infrastructure. The platform enables developers to build and scale modern software efficiently.",
        target_audience="Software engineers and development teams building modern applications.",
        contact_emails=[f"info@{domain}"],
        team_members=[
            TeamMember(name="Leadership Team", role="Executive", linkedin_url="")
        ],
        confidence_score=0.80 if len(pages_scraped) >= 3 else 0.50,
        pages_scraped=pages_scraped,
        tokens_used=int(total_kb * 10),
        estimated_cost_usd=0.00015,
    )


def display_summary_table(profiles: List[CompanyProfile]):
    """Displays a formatted Rich table summarizing the results."""
    table = Table(title="[bold green]Lead Enrichment Results (Milestone 2 Crawled)[/bold green]")
    table.add_column("Domain", style="cyan", no_wrap=True)
    table.add_column("Pages Scraped", style="yellow", justify="center")
    table.add_column("Overview (2 Sentences)", style="white")
    table.add_column("Target Audience (ICP)", style="yellow")
    table.add_column("Emails", style="magenta")
    table.add_column("Confidence", style="green", justify="right")

    for profile in profiles:
        emails = ", ".join(profile.contact_emails) if profile.contact_emails else "None"
        table.add_row(
            profile.domain,
            f"{len(profile.pages_scraped)}",
            profile.company_overview,
            profile.target_audience,
            emails,
            f"{profile.confidence_score:.2f}",
        )

    console.print(table)


async def async_main(domains: List[str]):
    console.print(
        Panel.fit(
            "[bold white]Autonomous Lead Enrichment Agent[/bold white]\n"
            "[cyan]Targeting:[/cyan] " + ", ".join(domains),
            border_style="blue",
        )
    )

    crawler = WebCrawler()
    results = []
    try:
        for domain in domains:
            profile = await process_domain(domain.strip(), crawler)
            results.append(profile)
            console.print(f"[bold green]✓ Completed crawl & processing for {domain}[/bold green]\n")
    finally:
        await crawler.close()

    display_summary_table(results)


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
    asyncio.run(async_main(args.domains))


if __name__ == "__main__":
    main()
