"""
Test script for Milestone 4 - LLM Extraction & Schema Validation.
Takes cleaned text from output/scratch/ and runs LLMExtractor with Gemini API,
producing output/output.json.
"""

import json
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import settings
from schema import CompanyProfile
from src.extractor import LLMExtractor

console = Console(force_terminal=True)
TARGET_DOMAINS = ["postman.com", "supabase.com", "vapi.ai"]


def test_extractor_milestone4():
    console.print("[bold green]====================================================[/bold green]")
    console.print("[bold green]  Milestone 4: Gemini LLM Extraction & Validation  [/bold green]")
    console.print("[bold green]====================================================[/bold green]\n")

    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel.fit(
                "[bold red]GEMINI_API_KEY is not set![/bold red]\n\n"
                "Please create a [yellow].env[/yellow] file in the project directory:\n"
                "[cyan]GEMINI_API_KEY=AIzaSy...[/cyan]\n\n"
                "Or export it in your environment: [cyan]$env:GEMINI_API_KEY='AIzaSy...'[/cyan]",
                border_style="red",
            )
        )
        return False

    extractor = LLMExtractor(api_key=api_key)
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_profiles = []

    for domain in TARGET_DOMAINS:
        clean_file = Path("output/scratch") / f"{domain}_clean.txt"
        if not clean_file.exists():
            console.print(f"[red]Cleaned text file not found: {clean_file}[/red]")
            continue

        cleaned_content = clean_file.read_text(encoding="utf-8", errors="ignore")
        estimated_tokens = len(cleaned_content) // 4

        # Read discovered URLs from scratch directory
        pages_dir = Path("output/scratch") / domain
        pages_scraped = [
            f"https://{domain}/{f.stem.replace('_', '/')}"
            for f in pages_dir.glob("*.html")
        ] if pages_dir.exists() else [f"https://{domain}"]

        console.print(f"\n[bold cyan]>>> Extracting intelligence for: {domain}[/bold cyan]")
        try:
            profile = extractor.extract(
                domain=domain,
                cleaned_content=cleaned_content,
                pages_scraped=pages_scraped,
                estimated_input_tokens=estimated_tokens,
            )
            extracted_profiles.append(profile)
            console.print(f"[bold green]✓ Extracted {domain}[/bold green] (Tokens: {profile.tokens_used}, Cost: ${profile.estimated_cost_usd:.5f}, Confidence: {profile.confidence_score})")
            console.print(f"  [bold]Overview:[/bold] {profile.company_overview}")
            console.print(f"  [bold]ICP:[/bold] {profile.target_audience}")
            console.print(f"  [bold]Emails:[/bold] {profile.contact_emails or 'None'}")
            team_str = ", ".join(f"{m.name} ({m.role})" for m in profile.team_members) if profile.team_members else "None"
            console.print(f"  [bold]Team:[/bold] {team_str}")

        except Exception as e:
            console.print(f"[bold red]✗ Extraction failed for {domain}: {e}[/bold red]")

    # Save to output/output.json
    output_json_path = output_dir / "output.json"
    data = [p.model_dump() for p in extracted_profiles]
    output_json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    console.print(f"\n[bold green]Saved {len(extracted_profiles)} profiles to {output_json_path.resolve()}[/bold green]")

    # Display Table
    table = Table(title="LLM Extracted Lead Intelligence (Gemini)")
    table.add_column("Domain", style="cyan", no_wrap=True)
    table.add_column("Overview (2 Sentences)", style="white")
    table.add_column("Target Audience (ICP)", style="yellow")
    table.add_column("Emails", style="magenta")
    table.add_column("Key Team", style="blue")
    table.add_column("Tokens", style="dim", justify="right")
    table.add_column("Cost ($)", style="dim", justify="right")
    table.add_column("Score", style="green", justify="right")

    for p in extracted_profiles:
        emails = ", ".join(p.contact_emails) if p.contact_emails else "None"
        team = ", ".join(f"{m.name} ({m.role})" for m in p.team_members) if p.team_members else "None"
        table.add_row(
            p.domain,
            p.company_overview,
            p.target_audience,
            emails,
            team,
            f"{p.tokens_used:,}",
            f"${p.estimated_cost_usd:.5f}",
            f"{p.confidence_score:.2f}",
        )

    console.print("\n")
    console.print(table)
    return True


if __name__ == "__main__":
    test_extractor_milestone4()
