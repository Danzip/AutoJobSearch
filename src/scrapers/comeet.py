from src.scrapers.base import BaseScraper, ScrapedJob
from src.scrapers.generic import GenericScraper, fetch_html
from src.scrapers.generic import extract_text


class ComeetScraper(BaseScraper):
    def scrape(self, url: str) -> ScrapedJob:
        soup = fetch_html(url)

        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

        location = ""
        loc_el = soup.select_one("[class*='location']") or soup.select_one(
            "[class*='city']"
        )
        if loc_el:
            location = loc_el.get_text(strip=True)

        description = extract_text(soup)
        return ScrapedJob(title=title, location=location, description=description)
