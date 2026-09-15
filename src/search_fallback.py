"""
External Search Fallback for Key Leadership LinkedIn Profiles.
Bonus feature: searches for external LinkedIn URLs if missing from direct website text.
"""

import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus

import httpx

from config import settings
from schema import TeamMember

logger = logging.getLogger(__name__)

LINKEDIN_URL_PATTERN = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?",
    re.IGNORECASE,
)


class LinkedInSearchFallback:
    """
    Looks up verified LinkedIn profiles for identified leadership members using
    Tavily search API or lightweight fallback web queries.
    """

    def __init__(self, tavily_api_key: Optional[str] = None):
        self.tavily_api_key = tavily_api_key or settings.tavily_api_key

    async def search_linkedin_tavily(self, name: str, company: str) -> Optional[str]:
        """Queries Tavily API for person's LinkedIn profile."""
        if not self.tavily_api_key:
            return None

        query = f'"{name}" "{company}" site:linkedin.com/in/'
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 3,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for result in data.get("results", []):
                        url = result.get("url", "")
                        match = LINKEDIN_URL_PATTERN.search(url)
                        if match:
                            return match.group(0)
        except Exception as e:
            logger.debug(f"Tavily search failed for {name} ({company}): {e}")
        return None

    async def search_linkedin_duckduckgo(self, name: str, company: str) -> Optional[str]:
        """Queries DuckDuckGo HTML for person's LinkedIn profile."""
        query = quote_plus(f"{name} {company} site:linkedin.com/in/")
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    matches = LINKEDIN_URL_PATTERN.findall(resp.text)
                    if matches:
                        return matches[0]
        except Exception as e:
            logger.debug(f"DuckDuckGo search fallback failed for {name}: {e}")
        return None

    async def enrich_team_member(self, member: TeamMember, company: str) -> TeamMember:
        """Enriches a team member with a discovered LinkedIn URL if currently empty."""
        if member.linkedin_url and member.linkedin_url.strip():
            return member

        # Skip generic placeholder names
        if any(w in member.name.lower() for w in ["leadership", "team", "executive", "founder & ceo"]):
            return member

        url = await self.search_linkedin_tavily(member.name, company)
        if not url:
            url = await self.search_linkedin_duckduckgo(member.name, company)

        if url:
            logger.info(f"Discovered external LinkedIn for {member.name}: {url}")
            member.linkedin_url = url
        return member

    async def enrich_team(self, team: List[TeamMember], company: str) -> List[TeamMember]:
        """Enriches all team members sequentially."""
        enriched = []
        for m in team:
            enriched.append(await self.enrich_team_member(m, company))
        return enriched
