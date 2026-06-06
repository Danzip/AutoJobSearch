"""
LinkedIn job page scraper.
Works on public /jobs/view/ pages without login.
LinkedIn sends a redirect to the login page for some roles - we fall back to
whatever text we can extract, and show a notice if the content is too short.
"""

import re

from src.scrapers.base import BaseScraper, ScrapedJob
from src.scrapers.generic import fetch_html, extract_text

# Selectors LinkedIn uses for job content (changes occasionally)
_TITLE_SELECTORS = [
    "h1.top-card-layout__title",
    "h1.t-24",
    "h1",
]
_COMPANY_SELECTORS = [
    "a.topcard__org-name-link",
    ".topcard__org-name-link",
    "span.topcard__flavor a",
]
_LOCATION_SELECTORS = [
    "span.topcard__flavor--bullet",
    ".topcard__flavor--bullet",
]
_DESC_SELECTORS = [
    ".description__text",
    ".show-more-less-html__markup",
    "[class*='description']",
]


class LinkedInScraper(BaseScraper):
    def scrape(self, url: str) -> ScrapedJob:
        # Normalise to the public /jobs/view/ format
        url = _normalise_url(url)
        soup = fetch_html(url)

        title = _pick(soup, _TITLE_SELECTORS)
        company = _pick(soup, _COMPANY_SELECTORS)
        location = _pick(soup, _LOCATION_SELECTORS)

        # Try description-specific selectors first, then fall back to generic
        desc_el = None
        for sel in _DESC_SELECTORS:
            desc_el = soup.select_one(sel)
            if desc_el and len(desc_el.get_text(strip=True)) > 100:
                break

        if desc_el:
            description = desc_el.get_text(separator="\n").strip()
        else:
            description = extract_text(soup)

        if len(description.strip()) < 150:
            description = (
                "[LinkedIn may have required login to view this posting. "
                "Content below may be incomplete - paste the full description manually.]\n\n"
                + description
            )

        from src.scrapers.date_utils import parse_relative_date
        posted_date = ""
        date_el = soup.find(string=re.compile(r"\d+\s*(hour|day|week|month|year)s?\s*ago", re.I))
        if date_el:
            posted_date = parse_relative_date(str(date_el))

        return ScrapedJob(
            title=title,
            company=company,
            location=location,
            description=description,
            source="linkedin",
            posted_date=posted_date,
        )


def _pick(soup, selectors: list[str]) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True)
    return ""


def _normalise_url(url: str) -> str:
    """Convert il.linkedin.com/jobs/view/... to www.linkedin.com/jobs/view/..."""
    return url.replace("il.linkedin.com", "www.linkedin.com")
