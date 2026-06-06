import re
import requests
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, ScrapedJob, ScraperError

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

CONTENT_SELECTORS = [
    "main",
    "article",
    "[class*='job-description']",
    "[id*='job-description']",
    "[class*='job-details']",
    "[id*='job-details']",
    "[class*='description']",
    "[class*='posting']",
]


def fetch_html(url: str, timeout: int = 15) -> BeautifulSoup:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ScraperError(f"Failed to fetch {url}: {e}") from e
    return BeautifulSoup(resp.text, "lxml")


def extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    for selector in CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el:
            return _clean(el.get_text(separator="\n"))

    # Fallback: largest <div> by text length
    divs = soup.find_all("div")
    if divs:
        best = max(divs, key=lambda d: len(d.get_text()))
        return _clean(best.get_text(separator="\n"))

    return _clean(soup.get_text(separator="\n"))


def _clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


class GenericScraper(BaseScraper):
    def scrape(self, url: str) -> ScrapedJob:
        soup = fetch_html(url)
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
        elif soup.title:
            title = soup.title.string or ""
        description = extract_text(soup)
        return ScrapedJob(title=title, description=description)
