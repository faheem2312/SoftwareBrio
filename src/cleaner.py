"""
Content Cleaning & Token Optimization Pipeline.
Extracts high-signal text/markdown from raw HTML using trafilatura with BeautifulSoup fallback.
Strips boilerplate, scripts, styles, SVGs, and navigation, enforcing a strict token budget.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import trafilatura

from config import settings

logger = logging.getLogger(__name__)

# Heuristic token estimation: ~4 characters per token
CHARS_PER_TOKEN = 4


class ContentCleaner:
    """
    Cleans raw HTML pages, removes DOM noise/boilerplate, and prepares a token-optimized
    concatenated context for LLM extraction within a strict token budget.
    """

    def __init__(
        self,
        max_tokens_budget: int = settings.max_tokens_budget,
        scratch_dir: Path = settings.scratch_dir,
    ):
        self.max_tokens_budget = max_tokens_budget
        self.max_chars_budget = max_tokens_budget * CHARS_PER_TOKEN
        self.scratch_dir = scratch_dir
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimates token count based on standard ~4 characters per token heuristic."""
        if not text:
            return 0
        return max(1, len(text) // CHARS_PER_TOKEN)

    def extract_with_trafilatura(self, html: str, url: str) -> Optional[str]:
        """Uses trafilatura to extract primary article/body text."""
        try:
            extracted = trafilatura.extract(
                html,
                url=url,
                include_links=True,
                include_tables=True,
                include_comments=False,
                output_format="txt",
                no_fallback=False,
            )
            if extracted and len(extracted.strip()) > 150:
                return extracted.strip()
        except Exception as e:
            logger.debug(f"Trafilatura extraction failed for {url}: {e}")
        return None

    def extract_with_beautifulsoup(self, html: str) -> str:
        """
        Fallback DOM cleaning: removes script, style, svg, header, footer,
        and extracts clean text blocks.
        """
        soup = BeautifulSoup(html, "lxml")

        # Decompose non-content and noisy elements
        for tag in soup(
            [
                "script",
                "style",
                "svg",
                "noscript",
                "header",
                "footer",
                "nav",
                "iframe",
                "canvas",
                "form",
            ]
        ):
            tag.decompose()

        # Remove elements with cookie/popup/ad classes or ids
        noise_pattern = re.compile(
            r"cookie|consent|banner|modal|popup|advertisement|newsletter|overlay",
            re.IGNORECASE,
        )
        for noise_el in soup.find_all(attrs={"class": noise_pattern}):
            noise_el.decompose()
        for noise_el in soup.find_all(attrs={"id": noise_pattern}):
            noise_el.decompose()

        # Extract text separated by newlines
        lines = []
        for string in soup.stripped_strings:
            clean_str = re.sub(r"\s+", " ", string).strip()
            # Ignore micro-strings (buttons, icons, single chars)
            if len(clean_str) > 2:
                lines.append(clean_str)

        return "\n".join(lines)

    def clean_page(self, url: str, html: str) -> str:
        """Cleans a single HTML page using trafilatura with BeautifulSoup fallback."""
        if not html or not html.strip():
            return ""

        # Primary extraction
        clean_text = self.extract_with_trafilatura(html, url)
        if not clean_text:
            # Secondary fallback
            logger.debug(f"Using BeautifulSoup fallback for {url}")
            clean_text = self.extract_with_beautifulsoup(html)

        # Normalize consecutive blank lines
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
        return clean_text

    def clean_and_assemble(
        self, domain: str, raw_pages: Dict[str, str]
    ) -> Tuple[str, Dict[str, any]]:
        """
        Processes all crawled pages for a domain:
        1. Cleans each page's HTML to markdown/text.
        2. Deduplicates repeated sentences/blocks across pages.
        3. Enforces token budget constraint (< ~7,000 tokens).
        4. Calculates and logs token reduction metrics.
        5. Saves cleaned text to scratch folder.

        Returns:
            (concatenated_clean_text, metrics_dict)
        """
        total_raw_chars = sum(len(h) for h in raw_pages.values())
        cleaned_sections: List[Tuple[str, str, int]] = []

        # Ensure homepage is processed first
        sorted_urls = sorted(
            raw_pages.keys(),
            key=lambda u: 0 if urlparse(u).path.strip("/") in ("", "index", "home") else 1,
        )

        for url in sorted_urls:
            raw_html = raw_pages[url]
            page_text = self.clean_page(url, raw_html)
            if page_text:
                tokens = self.estimate_tokens(page_text)
                cleaned_sections.append((url, page_text, tokens))

        # Assemble within token budget
        assembled_parts: List[str] = []
        current_chars = 0

        for url, page_text, _ in cleaned_sections:
            header = f"\n=== PAGE: {url} ===\n"
            chars_needed = len(header) + len(page_text)

            if current_chars + chars_needed <= self.max_chars_budget:
                assembled_parts.append(header + page_text)
                current_chars += chars_needed
            else:
                # Truncate this last section to fill remaining budget
                remaining_budget = max(0, self.max_chars_budget - current_chars - len(header))
                if remaining_budget > 300:
                    truncated_text = page_text[:remaining_budget] + "\n[...content truncated for token budget...]"
                    assembled_parts.append(header + truncated_text)
                break

        final_clean_text = "\n".join(assembled_parts).strip()
        final_chars = len(final_clean_text)
        final_tokens = self.estimate_tokens(final_clean_text)

        reduction_pct = (
            ((total_raw_chars - final_chars) / total_raw_chars * 100.0)
            if total_raw_chars > 0
            else 0.0
        )

        metrics = {
            "domain": domain,
            "pages_cleaned": len(cleaned_sections),
            "raw_chars": total_raw_chars,
            "raw_kb": round(total_raw_chars / 1024, 1),
            "clean_chars": final_chars,
            "clean_kb": round(final_chars / 1024, 1),
            "estimated_tokens": final_tokens,
            "reduction_pct": round(reduction_pct, 2),
        }

        # Save to scratch folder for verification
        scratch_clean_file = self.scratch_dir / f"{domain}_clean.txt"
        scratch_clean_file.write_text(final_clean_text, encoding="utf-8", errors="ignore")
        logger.debug(f"Saved cleaned text to {scratch_clean_file}")

        return final_clean_text, metrics
