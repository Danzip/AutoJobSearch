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
            page.goto(url, wait_until="domcontentloaded", timeout=_TIMEOUT)
            page.wait_for_timeout(4000)

            title       = _text(page, ".positionTitle, h1")
            location    = _text(page, ".positionLocation, [class*='location']")
            description = page.inner_text("body").strip()
            date_text   = _text(page, "[class*='date'], [class*='posted'], time")
            posted_date = parse_relative_date(date_text)

            # Closed job redirects to company listing: meaningful description won't be present
            if len(description) < 200:
                return ScrapedJob()

            # Use URL slug — DOM selectors pick up "All Jobs" navigation noise
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
            page.goto(base_url, wait_until="domcontentloaded", timeout=_TIMEOUT)
            page.wait_for_timeout(3000)

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


def scrape_batch(urls: list[str], workers: int = 6) -> list[ScrapedJob]:
    """Scrape multiple Comeet job URLs in parallel. Each thread owns its own browser."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, ScrapedJob] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {executor.submit(_playwright_scrape, url): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception:
                results[url] = ScrapedJob()
    return [results.get(url, ScrapedJob()) for url in urls]


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
