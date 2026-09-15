"""
Resilience & Fault Tolerance utilities.
Implements retry decorators with exponential backoff using tenacity,
and safe exception isolation to prevent pipeline crashes on bad domains.
"""

import logging
from typing import Any, Callable
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import httpx

from schema import CompanyProfile, TeamMember

logger = logging.getLogger(__name__)


# Retry decorator for network calls (httpx/Playwright) with exponential backoff
network_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, ConnectionError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


def create_degraded_profile(domain: str, error_message: str) -> CompanyProfile:
    """
    Constructs a valid, degraded CompanyProfile when a domain fails completely
    (e.g., DNS resolution failure, 404, bot blocking, or persistent timeout).
    Ensures the pipeline never crashes mid-batch.
    """
    logger.warning(f"Constructing degraded profile for {domain} due to: {error_message}")
    return CompanyProfile(
        domain=domain,
        company_overview=f"Content extraction unavailable for {domain}. Access was restricted, blocked, or timed out during crawling.",
        target_audience="Not specified in available content",
        contact_emails=[],
        team_members=[],
        confidence_score=0.10,
        pages_scraped=[],
        tokens_used=0,
        estimated_cost_usd=0.0,
    )
