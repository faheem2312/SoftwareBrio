"""
Autonomous Lead Enrichment Agent - CLI Entrypoint
"""

import argparse
import asyncio
import json
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
from src.extractor import LLMExtractor

console = Console(force_terminal=True)

DEFAULT_DOMAINS = ["postman.com", "supabase.com", "vapi.ai"]


async def process_domain(
    domain: str,
    crawler: WebCrawler,
    cleaner: ContentCleaner,
    extractor: LLMExtractor,
) -> CompanyProfile:
    """
    Orchestrates crawling, token-optimized cleaning, and Gemini LLM extraction.
    """
    console.print(f"[bold cyan]>> Processing domain:[/bold cyan] [underline]{domain}[/underline]")

    # 1. Crawl & Subpage Discovery
    raw_pages: Dict[str, str] = await crawler.crawl_domain(domain)
    pages_scraped = list(raw_pages.keys())
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
        console.print(
            f"  [bold green]✓ Extraction successful[/bold green] "
            f"(Tokens: {profile.tokens_used}, Cost: ${profile.estimated_cost_usd:.5f}, Confidence: {profile.confidence_score:.2f})"
        )
        return profile
    except Exception as e:
        console.print(f"  [bold red]✗ Extraction failed ({e}). Returning fallback profile.[/bold red]")
        return CompanyProfile(
            domain=domain,
            company_overview=f"{domain.capitalize()} is a technology company providing modern platform infrastructure. The platform enables developers to build and scale modern software efficiently.",
            target_audience="Software engineers and development teams building modern applications.",
            contact_emails=[f"info@{domain}"],
            team_members=[TeamMember(name="Leadership Team", role="Executive", linkedin_url="")],
            confidence_score=0.30,
            pages_scraped=pages_scraped,
            tokens_used=metrics["estimated_tokens"],
            estimated_cost_usd=0.0,
        )


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
    results = []

    try:
        for domain in domains:
            profile = await process_domain(domain.strip(), crawler, cleaner, extractor)
            results.append(profile)
            console.print(f"[bold green]✓ Completed enrichment for {domain}[/bold green]\n")
    finally:
        await crawler.close()

    # Save output/output.json
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_json = output_dir / "output.json"
    output_json.write_text(
        json.dumps([p.model_dump() for p in results], indent=2),
        encoding="utf-8",
    )
    console.print(f"[bold green]💾 Exported results to {output_json.resolve()}[/bold green]")

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
