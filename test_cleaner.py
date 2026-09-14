"""
Test script for Milestone 3 - Content Cleaning & Token Optimization.
Loads raw HTML from output/scratch/ and executes the cleaner pipeline,
measuring and verifying token reduction percentages and clean text output.
"""

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

from src.cleaner import ContentCleaner

console = Console(force_terminal=True)
TARGET_DOMAINS = ["postman.com", "supabase.com", "vapi.ai"]


def test_cleaner_milestone3():
    console.print("[bold green]======================================================[/bold green]")
    console.print("[bold green]  Milestone 3: Content Cleaning & Token Optimization  [/bold green]")
    console.print("[bold green]======================================================[/bold green]\n")

    cleaner = ContentCleaner()
    table = Table(title="Content Cleaning & Token Reduction Metrics")
    table.add_column("Domain", style="cyan", no_wrap=True)
    table.add_column("Raw Size (KB)", style="red", justify="right")
    table.add_column("Clean Size (KB)", style="green", justify="right")
    table.add_column("Est. Tokens", style="yellow", justify="right")
    table.add_column("Token Budget", style="blue", justify="right")
    table.add_column("Reduction %", style="bold magenta", justify="right")

    for domain in TARGET_DOMAINS:
        domain_dir = Path("output/scratch") / domain
        if not domain_dir.exists():
            console.print(f"[red]Directory not found: {domain_dir}[/red]")
            continue

        raw_pages = {}
        for file in domain_dir.glob("*.html"):
            url = f"https://{domain}/{file.stem.replace('_', '/')}"
            raw_pages[url] = file.read_text(encoding="utf-8", errors="ignore")

        clean_text, metrics = cleaner.clean_and_assemble(domain, raw_pages)

        table.add_row(
            domain,
            f"{metrics['raw_kb']} KB",
            f"{metrics['clean_kb']} KB",
            f"{metrics['estimated_tokens']:,}",
            f"{cleaner.max_tokens_budget:,}",
            f"{metrics['reduction_pct']}%",
        )

        console.print(f"[bold cyan]>> {domain}:[/bold cyan] Reduced from {metrics['raw_kb']} KB to {metrics['clean_kb']} KB ({metrics['estimated_tokens']} tokens, [bold green]{metrics['reduction_pct']}% reduction[/bold green])")
        preview = clean_text[:300].replace("\n", " ")
        console.print(f"  [dim]Preview: {preview}...[/dim]\n")

    console.print("\n")
    console.print(table)


if __name__ == "__main__":
    test_cleaner_milestone3()
