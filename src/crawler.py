"""
Web Crawler & Subpage Discovery module.
Combines Playwright async browser automation with httpx fallback,
sitemap.xml parsing, and keyword-based internal link discovery.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger(__name__)

# Target keywords to prioritize for lead enrichment
SUBPAGE_KEYWORDS = [
    "about",
    "team",
    "people",
    "leadership",
    "company",
    "contact",
    "pricing",
    "careers",
    "press",
    "about-us",
    "our-team",
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class WebCrawler:
    """
    Crawls target domains, discovers high-value subpages (about, team, pricing, contact),
    and retrieves rendered HTML using Playwright or httpx fallback.
    """

    def __init__(
        self,
        max_subpages: int = settings.max_subpages,
        timeout_ms: int = settings.page_timeout_ms,
        headless: bool = settings.headless,
        scratch_dir: Path = settings.scratch_dir,
    ):
        self.max_subpages = max_subpages
        self.timeout_ms = timeout_ms
        self.timeout_sec = timeout_ms / 1000.0
        self.headless = headless
        self.scratch_dir = scratch_dir
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser = None

    async def _init_browser(self):
        """Attempts to initialize Playwright Chromium browser."""
        if self._browser is not None:
            return self._browser

        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            logger.info("Playwright Chromium browser initialized successfully.")
        except Exception as e:
            logger.warning(f"Playwright initialization failed ({e}). Falling back to httpx.")
            self._browser = None
        return self._browser

    async def close(self):
        """Closes browser instances and cleanup."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def fetch_page_playwright(self, url: str) -> Optional[str]:
        """Fetches and renders a page using Playwright."""
        browser = await self._init_browser()
        if not browser:
            return None

        context = None
        page = None
        try:
            context = await browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()
            # Navigate with domcontentloaded wait
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            # Brief wait for client-side hydration
            await page.wait_for_timeout(1500)
            content = await page.content()
            return content
        except Exception as e:
            logger.warning(f"Playwright fetch failed for {url}: {e}")
            return None
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

    async def fetch_page_httpx(self, url: str) -> Optional[str]:
        """Fallback page fetcher using async httpx."""
        try:
            async with httpx.AsyncClient(
                headers=DEFAULT_HEADERS,
                timeout=self.timeout_sec,
                follow_redirects=True,
                verify=False,
            ) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.text
                logger.warning(f"httpx returned status {response.status_code} for {url}")
                return None
        except Exception as e:
            logger.warning(f"httpx fetch failed for {url}: {e}")
            return None

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetches page HTML trying Playwright first, then httpx fallback."""
        html = await self.fetch_page_playwright(url)
        if not html or len(html.strip()) < 200:
            logger.info(f"Retrying {url} with httpx...")
            html = await self.fetch_page_httpx(url)
        return html

    async def discover_from_sitemap(self, domain: str) -> List[str]:
        """Discovers candidate subpages from sitemap.xml."""
        sitemap_urls = [
            f"https://{domain}/sitemap.xml",
            f"https://{domain}/sitemap_index.xml",
            f"https://www.{domain}/sitemap.xml",
        ]

        discovered: List[str] = []
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=10.0, follow_redirects=True, verify=False) as client:
            for sitemap_url in sitemap_urls:
                try:
                    resp = await client.get(sitemap_url)
                    if resp.status_code == 200 and ("xml" in resp.headers.get("content-type", "") or resp.text.startswith("<?xml")):
                        # Parse XML loc entries
                        root = ET.fromstring(resp.content)
                        # Extract all <loc> text regardless of namespace
                        for elem in root.iter():
                            if elem.tag.endswith("loc") and elem.text:
                                loc = elem.text.strip()
                                path_lower = urlparse(loc).path.lower()
                                # Ignore nested sitemaps or feed files
                                if path_lower.endswith(".xml") or path_lower.endswith(".xml.gz") or path_lower.endswith(".rss"):
                                    continue
                                if any(kw in path_lower for kw in SUBPAGE_KEYWORDS):
                                    if loc not in discovered:
                                        discovered.append(loc)
                        if discovered:
                            logger.info(f"Found {len(discovered)} relevant pages in sitemap for {domain}")
                            return discovered[: self.max_subpages]
                except Exception as e:
                    logger.debug(f"Sitemap check failed for {sitemap_url}: {e}")
        return discovered

    def discover_from_html_links(self, base_url: str, html: str) -> List[str]:
        """Extracts internal links from HTML matching enrichment keywords."""
        soup = BeautifulSoup(html, "lxml")
        base_domain = urlparse(base_url).netloc.lower().replace("www.", "")
        discovered: List[str] = []
        seen_paths: Set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            # Normalize to absolute URL
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            parsed_domain = parsed.netloc.lower().replace("www.", "")

            # Ensure internal domain link
            if parsed_domain != base_domain:
                continue

            # Strip queries and anchors
            clean_path = parsed.path.rstrip("/").lower()
            if not clean_path or clean_path in seen_paths:
                continue

            # Check if path contains enrichment keywords
            if any(re.search(rf"\b{kw}\b", clean_path) or kw in clean_path for kw in SUBPAGE_KEYWORDS):
                seen_paths.add(clean_path)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                discovered.append(clean_url)
                if len(discovered) >= self.max_subpages:
                    break

        return discovered

    def _save_scratch_html(self, domain: str, url: str, html: str):
        """Saves raw HTML to scratch directory for manual inspection."""
        domain_scratch = self.scratch_dir / domain
        domain_scratch.mkdir(parents=True, exist_ok=True)
        # Sanitize filename from URL path
        parsed = urlparse(url)
        path_slug = parsed.path.strip("/").replace("/", "_")
        filename = f"{path_slug or 'index'}.html"
        file_path = domain_scratch / filename
        file_path.write_text(html, encoding="utf-8", errors="ignore")
        logger.debug(f"Saved raw HTML to {file_path}")

    async def crawl_domain(self, domain: str) -> Dict[str, str]:
        """
        Crawls a company domain:
        1. Fetches homepage.
        2. Discovers subpages via sitemap or homepage links.
        3. Fetches up to max_subpages.
        4. Dumps raw HTML to scratch folder.
        Returns a dict of {url: raw_html}.
        """
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").strip("/")
        homepage_url = f"https://{clean_domain}"
        results: Dict[str, str] = {}

        logger.info(f"Crawling homepage: {homepage_url}")
        home_html = await self.fetch_page(homepage_url)
        if not home_html:
            # Try with www. prefix
            homepage_url = f"https://www.{clean_domain}"
            home_html = await self.fetch_page(homepage_url)

        if not home_html:
            logger.error(f"Failed to fetch homepage for {clean_domain}")
            return results

        results[homepage_url] = home_html
        self._save_scratch_html(clean_domain, homepage_url, home_html)

        # Subpage discovery: sitemap first, then homepage HTML links fallback
        subpages = await self.discover_from_sitemap(clean_domain)
        if not subpages:
            logger.info(f"Sitemap empty or not found for {clean_domain}. Falling back to HTML link discovery.")
            subpages = self.discover_from_html_links(homepage_url, home_html)

        logger.info(f"Discovered {len(subpages)} candidate subpages for {clean_domain}: {subpages}")

        # Fetch discovered subpages concurrently
        async def _fetch_subpage(url: str):
            sub_html = await self.fetch_page(url)
            if sub_html:
                results[url] = sub_html
                self._save_scratch_html(clean_domain, url, sub_html)

        fetch_tasks = [_fetch_subpage(url) for url in subpages[: self.max_subpages]]
        if fetch_tasks:
            await asyncio.gather(*fetch_tasks)

        return results
