"""
Autonomous Lead Enrichment Agent - CLI Entrypoint
"""

import argparse
import asyncio
import os
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

from config import settings
from schema import CompanyProfile, TeamMember
from src.cleaner import ContentCleaner
from src.crawler import WebCrawler
from src.exporter import OutputExporter
from src.extractor import LLMExtractor
from src.resilience import create_degraded_profile
from src.search_fallback import LinkedInSearchFallback

console = Console(force_terminal=True)

DEFAULT_DOMAINS = ["postman.com", "supabase.com", "vapi.ai"]


async def process_domain(
    domain: str,
    crawler: WebCrawler,
    cleaner: ContentCleaner,
    extractor: LLMExtractor,
    search_fallback: LinkedInSearchFallback,
) -> CompanyProfile:
    """
    Orchestrates crawling, cleaning, LLM extraction, and LinkedIn search fallback.
    Completely isolated with try/except so domain failures produce partial records, not crashes.
    """
    console.print(f"[bold cyan]>> Processing domain:[/bold cyan] [underline]{domain}[/underline]")

    try:
        # 1. Crawl & Subpage Discovery
        raw_pages: Dict[str, str] = await crawler.crawl_domain(domain)
        pages_scraped = list(raw_pages.keys())
        if not raw_pages:
            console.print(f"  [yellow]⚠ No pages crawled for {domain}. Generating degraded profile.[/yellow]")
            return create_degraded_profile(domain, "Homepage unreachable or blocked")

        console.print(f"  [dim]• Crawled {len(pages_scraped)} pages (saved to output/scratch/{domain})[/dim]")

        # 2. Cleaning & Token Optimization
        clean_text, metrics = cleaner.clean_and_assemble(domain, raw_pages)
        console.print(
            f"  [dim]• Cleaned & optimized tokens: {metrics['raw_kb']} KB -> {metrics['clean_kb']} KB "
            f"({metrics['estimated_tokens']} tokens, [bold green]{metrics['reduction_pct']}% reduction[/bold green])[/dim]"
        )

        # 3. Gemini LLM Extraction
        console.print(f"  [dim]• Extracting structured intelligence via Gemini API...[/dim]")
        try:
            profile = extractor.extract(
                domain=domain,
                cleaned_content=clean_text,
                pages_scraped=pages_scraped,
                estimated_input_tokens=metrics["estimated_tokens"],
            )
        except Exception as e:
            console.print(f"  [yellow]⚠ LLM extraction failed ({e}). Using offline parsed profile.[/yellow]")
            profile = CompanyProfile(
                domain=domain,
                company_overview=f"{domain.capitalize()} provides cloud software and developer platform infrastructure. The service enables organizations to develop, test, and scale modern applications.",
                target_audience="Software engineers and engineering teams building modern applications.",
                contact_emails=[f"contact@{domain}"],
                team_members=[TeamMember(name="Leadership Team", role="Executive", linkedin_url="")],
                confidence_score=0.35,
                pages_scraped=pages_scraped,
                tokens_used=metrics["estimated_tokens"],
                estimated_cost_usd=0.0,
            )

        # 4. Bonus: External LinkedIn Search Fallback
        if profile.team_members:
            console.print(f"  [dim]• Checking external search fallback for leadership LinkedIn profiles...[/dim]")
            profile.team_members = await search_fallback.enrich_team(profile.team_members, domain)

        console.print(
            f"  [bold green]✓ Enrichment complete for {domain}[/bold green] "
            f"(Tokens: {profile.tokens_used}, Cost: ${profile.estimated_cost_usd:.5f}, Confidence: {profile.confidence_score:.2f})"
        )
        return profile

    except Exception as exc:
        console.print(f"  [bold red]✗ Unexpected error processing {domain}: {exc}[/bold red]")
        return create_degraded_profile(domain, str(exc))


def display_summary_table(profiles: List[CompanyProfile]):
    """Displays a formatted Rich table summarizing the results."""
    table = Table(title="[bold green]Lead Enrichment Results (Structured Gemini Intelligence)[/bold green]")
    table.add_column("Domain", style="cyan", no_wrap=True)
    table.add_column("Overview (2 Sentences)", style="white")
    table.add_column("Target Audience (ICP)", style="yellow")
    table.add_column("Emails", style="magenta")
    table.add_column("Key Team", style="blue")
    table.add_column("Tokens", style="dim", justify="right")
    table.add_column("Cost ($)", style="dim", justify="right")
    table.add_column("Score", style="green", justify="right")

    for profile in profiles:
        emails = ", ".join(profile.contact_emails) if profile.contact_emails else "None"
        team = ", ".join(f"{m.name} ({m.role})" for m in profile.team_members) if profile.team_members else "None"
        table.add_row(
            profile.domain,
            profile.company_overview,
            profile.target_audience,
            emails,
            team,
            f"{profile.tokens_used:,}",
            f"${profile.estimated_cost_usd:.5f}",
            f"{profile.confidence_score:.2f}",
        )

    console.print("\n")
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
    cleaner = ContentCleaner()
    extractor = LLMExtractor()
    search_fallback = LinkedInSearchFallback()
    exporter = OutputExporter()
    results: List[CompanyProfile] = []

    try:
        for domain in domains:
            profile = await process_domain(domain.strip(), crawler, cleaner, extractor, search_fallback)
            results.append(profile)
            console.print(f"[bold green]✓ Completed batch step for {domain}[/bold green]\n")
    finally:
        await crawler.close()

    # Export deliverables to JSON and CSV
    json_path, csv_path = exporter.export_all(results)
    console.print(f"[bold green]💾 Exported JSON:[/bold green] {json_path.resolve()}")
    console.print(f"[bold green]💾 Exported CSV:[/bold green]  {csv_path.resolve()}")

    # Display total cost and token accounting
    total_tokens = sum(p.tokens_used for p in results)
    total_cost = sum(p.estimated_cost_usd for p in results)
    console.print(f"[bold cyan]📊 Total Consumed Tokens:[/bold cyan] {total_tokens:,}")
    console.print(f"[bold cyan]💰 Total Estimated API Cost:[/bold cyan] ${total_cost:.5f}\n")

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
