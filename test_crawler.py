"""
Test script for Milestone 2 - Crawler & Subpage Discovery.
Crawls postman.com, supabase.com, and vapi.ai, saving raw HTML to output/scratch/.
"""

import asyncio
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.crawler import WebCrawler

console = Console(force_terminal=True)
TARGET_DOMAINS = ["postman.com", "supabase.com", "vapi.ai"]


async def test_crawler_milestone2():
    console.print("[bold green]====================================================[/bold green]")
    console.print("[bold green]  Milestone 2: Crawler & Subpage Discovery Testing  [/bold green]")
    console.print("[bold green]====================================================[/bold green]\n")

    crawler = WebCrawler(max_subpages=4, timeout_ms=15000)
    summary_table = Table(title="Crawler Discovery & Scratch Dump Summary")
    summary_table.add_column("Domain", style="cyan", no_wrap=True)
    summary_table.add_column("Pages Discovered", style="yellow")
    summary_table.add_column("Total HTML Size (KB)", style="magenta", justify="right")
    summary_table.add_column("Scratch Folder Location", style="white")

    try:
        for domain in TARGET_DOMAINS:
            console.print(f"\n[bold cyan]>>> Crawling domain: {domain}[/bold cyan]")
            pages = await crawler.crawl_domain(domain)
            total_bytes = sum(len(content.encode("utf-8")) for content in pages.values())
            size_kb = total_bytes / 1024

            scratch_path = Path("output/scratch") / domain
            summary_table.add_row(
                domain,
                f"{len(pages)} pages",
                f"{size_kb:.1f} KB",
                str(scratch_path.resolve()),
            )

            for url in pages.keys():
                console.print(f"  [dim]• Fetched & Dumped:[/dim] [underline]{url}[/underline]")

    finally:
        await crawler.close()

    console.print("\n")
    console.print(summary_table)


if __name__ == "__main__":
    asyncio.run(test_crawler_milestone2())
