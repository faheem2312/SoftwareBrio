"""
Pydantic v2 data models for structured lead enrichment extraction.
Strictly adheres to anti-hallucination guarantees and confidence score rubrics.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class TeamMember(BaseModel):
    name: str = Field(
        ...,
        description="Full name of the team member or key leader."
    )
    role: str = Field(
        ...,
        description="Official role, title, or position within the company."
    )
    linkedin_url: Optional[str] = Field(
        default="",
        description="Explicitly discovered LinkedIn profile URL. Empty string if not present."
    )


class CompanyProfile(BaseModel):
    domain: str = Field(
        default="",
        description="The domain of the company analyzed."
    )
    company_overview: str = Field(
        ...,
        description="Exactly 2 factual, neutral sentences describing what the company does and its core product/category."
    )
    target_audience: str = Field(
        ...,
        description="Ideal Customer Profile (ICP): who the product or service is built for."
    )
    contact_emails: List[str] = Field(
        default_factory=list,
        description="Deduplicated list of public/generic contact emails found verbatim in the content."
    )
    team_members: List[TeamMember] = Field(
        default_factory=list,
        description="Key leadership or team members identified with explicit names and roles."
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Completeness and grounding score between 0.0 and 1.0 based on available data quality."
    )
    pages_scraped: List[str] = Field(
        default_factory=list,
        description="List of URLs/subpages scraped and analyzed."
    )
    tokens_used: int = Field(
        default=0,
        description="Total tokens consumed during processing and LLM extraction."
    )
    estimated_cost_usd: float = Field(
        default=0.0,
        description="Estimated API cost in USD based on model pricing."
    )

    @field_validator("contact_emails", mode="before")
    @classmethod
    def deduplicate_emails(cls, v):
        import re
        email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$")
        if isinstance(v, list):
            seen = set()
            unique_emails = []
            for email in v:
                clean_email = str(email).strip().lower()
                if clean_email and clean_email not in seen and email_regex.match(clean_email):
                    seen.add(clean_email)
                    unique_emails.append(clean_email)
            return unique_emails
        return v
