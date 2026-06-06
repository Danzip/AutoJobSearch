from src.scrapers.base import BaseScraper, ScrapedJob
from src.scrapers.generic import GenericScraper


class WorkdayScraper(BaseScraper):
    """
    Workday pages are JavaScript-rendered — BeautifulSoup will capture partial content.
    The user should paste the full job description manually if the scrape is incomplete.
    """

    def scrape(self, url: str) -> ScrapedJob:
        job = GenericScraper().scrape(url)
        if len(job.description) < 200:
            job.description = (
                "[Workday pages are JS-rendered — content may be incomplete. "
                "Please paste the full job description below.]\n\n" + job.description
            )
        return job
