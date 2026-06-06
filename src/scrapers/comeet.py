"""
Comeet scraper using Playwright (JS-rendered Angular app).

Requires system deps:  sudo /path/to/.venv/bin/python -m playwright install-deps

Two modes:
  - Specific job URL  → scrapes that job's title + description
  - Company page URL  → returns empty (job was closed/redirected); use
                        ComeetCompanySearch for discovery instead
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
            page.wait_for_timeout(2000)

            # Detect if we landed on a company listing (job is closed/redirected)
            if page.query_selector(".positionsList, .positionItem"):
                return ScrapedJob()  # empty → batch will skip (too short)

            # Specific job page selectors
            title    = _text(page, ".positionTitle, h1")
            company  = _text(page, ".companyName, .company-name, [class*='company']")
            location = _text(page, ".positionLocation, [class*='location'], .fa-map-marker")
            desc_el  = (
                page.query_selector(".positionDetails, .userDesignedContent")
                or page.query_selector("[class*='description']")
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


def scrape_company_page(company_slug: str) -> list[dict]:
    """
    Scrape all current openings from a Comeet company page.
    Returns list of {title, location, url} dicts.
    """
    from playwright.sync_api import sync_playwright

    base_url = f"https://www.comeet.com/jobs/{company_slug}"
    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(base_url, wait_until="networkidle", timeout=_TIMEOUT)
            page.wait_for_timeout(2000)

            items = page.query_selector_all(".positionItem")
            for item in items:
                # positionItem is the <a> tag itself
                href     = item.get_attribute("href") or ""
                title_el = item.query_selector(".positionLink, .positionTitle")
                loc_li   = item.query_selector(".positionDetails li")
                title    = title_el.inner_text().strip() if title_el else ""
                location = loc_li.inner_text().strip() if loc_li else ""
                if title and href:
                    jobs.append({"title": title, "location": location, "url": href})
        finally:
            browser.close()

    return jobs


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
                    f"[Comeet requires Playwright (run: sudo python -m playwright install-deps). "
                    f"Error: {exc}]\n\n" + job.description
                )
            return job
