"""
Workday scraper using Workday's internal JSON API instead of BeautifulSoup.

Workday job URLs follow:
  https://{sub}.myworkdayjobs.com/en-US/{board}/job/{location}/{title}_{id}

The API endpoint is:
  GET https://{sub}.myworkdayjobs.com/wday/cxs/{company}/{board}/job/{location}/{title}_{id}

Returns JSON with jobPostingInfo.jobDescription (HTML).
"""
import re
import requests
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, ScrapedJob
from src.scrapers.generic import GenericScraper

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# https://intel.wd1.myworkdayjobs.com/en-US/External/job/Israel.../Title_JR123
_URL_RE = re.compile(
    r"https?://(?P<sub>[^.]+\.wd\d+)\.myworkdayjobs\.com"
    r"(?:/[^/]+)?"           # optional /en-US or /en-GB
    r"/(?P<board>[^/]+)"
    r"(?P<path>/job/.+)"
)


def _api_url(sub: str, board: str, path: str) -> tuple[str, str]:
    """Return (api_url, company_slug). company is the first segment of the sub."""
    company = sub.split(".")[0]
    api = f"https://{sub}.myworkdayjobs.com/wday/cxs/{company}/{board}{path}"
    return api, company


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n").strip()


class WorkdayScraper(BaseScraper):
    def scrape(self, url: str) -> ScrapedJob:
        m = _URL_RE.match(url)
        if m:
            api_url, _ = _api_url(m.group("sub"), m.group("board"), m.group("path"))
            try:
                r = requests.get(api_url, headers=_HEADERS, timeout=12)
                if r.status_code == 200:
                    data = r.json()
                    info = data.get("jobPostingInfo", {})
                    org = data.get("hiringOrganization", {})
                    desc_html = info.get("jobDescription", "")
                    return ScrapedJob(
                        title=info.get("title", ""),
                        company=org.get("name", ""),
                        location=info.get("locationsText", ""),
                        description=_html_to_text(desc_html),
                    )
            except Exception:
                pass  # fall through to generic

        # Fallback: generic scrape with notice
        job = GenericScraper().scrape(url)
        if len(job.description) < 200:
            job.description = (
                "[Workday page could not be scraped via API — content may be incomplete. "
                "Paste the full job description manually if needed.]\n\n" + job.description
            )
        return job
