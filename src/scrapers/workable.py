from src.scrapers.base import BaseScraper, ScrapedJob
from src.scrapers.generic import GenericScraper, fetch_html


class WorkableScraper(BaseScraper):
    def scrape(self, url: str) -> ScrapedJob:
        soup = fetch_html(url)

        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

        location = ""
        loc_el = soup.select_one("[data-ui='job-location']") or soup.select_one(
            "[class*='location']"
        )
        if loc_el:
            location = loc_el.get_text(strip=True)

        company = ""
        company_el = soup.select_one("[class*='company']") or soup.select_one(
            "[data-ui='company-name']"
        )
        if company_el:
            company = company_el.get_text(strip=True)

        from src.scrapers.generic import extract_text
        description = extract_text(soup)

        return ScrapedJob(title=title, company=company, location=location, description=description)
