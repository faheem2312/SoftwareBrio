"""
Unit tests for Pydantic schema validation, anti-hallucination rules, and cleaner.
"""

import pytest
from pydantic import ValidationError
from schema import CompanyProfile, TeamMember
from src.cleaner import ContentCleaner


def test_company_profile_valid():
    profile = CompanyProfile(
        domain="example.com",
        company_overview="Example Inc develops cloud tools. It serves enterprise teams globally.",
        target_audience="Enterprise software engineers.",
        contact_emails=["Contact@Example.com", "contact@example.com", "sales@example.com"],
        team_members=[
            TeamMember(name="Alice Doe", role="CTO", linkedin_url="https://linkedin.com/in/alicedoe")
        ],
        confidence_score=0.95,
        pages_scraped=["https://example.com"],
        tokens_used=1500,
        estimated_cost_usd=0.0001,
    )

    # Check deduplication of emails
    assert len(profile.contact_emails) == 2
    assert "contact@example.com" in profile.contact_emails
    assert "sales@example.com" in profile.contact_emails
    assert profile.confidence_score == 0.95


def test_confidence_score_bounds():
    # Confidence score > 1.0 should raise ValidationError
    with pytest.raises(ValidationError):
        CompanyProfile(
            company_overview="Sentence one. Sentence two.",
            target_audience="Developers",
            confidence_score=1.5,
        )

    # Confidence score < 0.0 should raise ValidationError
    with pytest.raises(ValidationError):
        CompanyProfile(
            company_overview="Sentence one. Sentence two.",
            target_audience="Developers",
            confidence_score=-0.1,
        )


def test_content_cleaner_token_reduction():
    cleaner = ContentCleaner(max_tokens_budget=1000)
    raw_html = """
    <html>
        <head><title>Test Page</title><script>console.log('noisy script');</script></head>
        <style>.body { color: red; }</style>
        <body>
            <header><nav><a href="/home">Home</a></nav></header>
            <main>
                <h1>Welcome to Acme Cloud</h1>
                <p>Acme Cloud provides scalable database hosting for modern developers.</p>
                <p>Contact our support team at support@acme.com.</p>
            </main>
            <footer><p>© 2026 Acme Corp. All rights reserved.</p></footer>
        </body>
    </html>
    """
    clean_text = cleaner.clean_page("https://acme.com", raw_html)
    assert "noisy script" not in clean_text
    assert "scalable database hosting" in clean_text
    assert cleaner.estimate_tokens(clean_text) < len(raw_html) // 4
