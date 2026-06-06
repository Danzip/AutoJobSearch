import re
import requests
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, ScrapedJob, ScraperError

_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"


def _parse_greenhouse_url(url: str):
    # boards.greenhouse.io/company/jobs/123456
    m = re.search(r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    # job-boards.greenhouse.io/company/jobs/123456
    m = re.search(r"job-boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


class GreenhouseScraper(BaseScraper):
    def scrape(self, url: str) -> ScrapedJob:
        board, job_id = _parse_greenhouse_url(url)
        if board and job_id:
            return self._scrape_api(board, job_id)
        # Fallback to generic HTML scraping
        from src.scrapers.generic import GenericScraper
        return GenericScraper().scrape(url)

    def _scrape_api(self, board: str, job_id: str) -> ScrapedJob:
        api_url = _API.format(board=board, job_id=job_id)
        try:
            resp = requests.get(api_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ScraperError(f"Greenhouse API error: {e}") from e

        from src.scrapers.date_utils import parse_relative_date
        title = data.get("title", "")
        location = data.get("location", {}).get("name", "")
        company = board.replace("-", " ").title()
        raw_html = data.get("content", "")
        description = BeautifulSoup(raw_html, "lxml").get_text(separator="\n").strip()
        posted_date = parse_relative_date(data.get("updated_at", ""))

        return ScrapedJob(
            title=title,
            company=company,
            location=location,
            description=description,
            posted_date=posted_date,
        )
