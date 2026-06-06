"""
Comeet scraper using Playwright (JS-rendered Angular app).

Requires system deps:  sudo playwright install-deps
"""
import re

from src.scrapers.base import BaseScraper, ScrapedJob
from src.scrapers.date_utils import parse_relative_date

_TIMEOUT = 20_000  # ms


def _playwright_scrape(url: str) -> ScrapedJob:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=_TIMEOUT)

            # Wait for Angular to render job content
            page.wait_for_selector(".position-title, h1, [class*='position']", timeout=_TIMEOUT)

            title    = _text(page, ".position-title, h1.title, h1")
            company  = _text(page, ".company-name, [class*='company'], .employer-name")
            location = _text(page, ".position-location, [class*='location']")

            desc_el = (
                page.query_selector(".position-description")
                or page.query_selector("[class*='description']")
                or page.query_selector(".details-section")
            )
            description = desc_el.inner_text().strip() if desc_el else page.inner_text("body")

            date_text   = _text(page, "[class*='date'], [class*='posted'], time")
            posted_date = parse_relative_date(date_text)

            if not company:
                m = re.search(r"comeet\.com/jobs/([^/]+)", url)
                company = m.group(1).replace("-", " ").title() if m else ""

        finally:
            browser.close()

    return ScrapedJob(
        title=title,
        company=company,
        location=location,
        description=description,
        source="comeet",
        posted_date=posted_date,
    )


def _text(page, selector: str) -> str:
    for sel in selector.split(","):
        el = page.query_selector(sel.strip())
        if el:
            t = el.inner_text().strip()
            if t:
                return t
    return ""


class ComeetScraper(BaseScraper):
    def scrape(self, url: str) -> ScrapedJob:
        try:
            return _playwright_scrape(url)
        except Exception as exc:
            from src.scrapers.generic import GenericScraper
            job = GenericScraper().scrape(url)
            if len(job.description) < 150:
                job.description = (
                    f"[Comeet requires Playwright (run: sudo playwright install-deps). "
                    f"Error: {exc}]\n\n" + job.description
                )
            return job
