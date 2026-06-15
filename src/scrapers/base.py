import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


class ScraperError(Exception):
    pass


@dataclass
class ScrapedJob:
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    source: str = "generic"
    posted_date: str = ""   # ISO date string YYYY-MM-DD, empty if unknown


class BaseScraper(ABC):
    @abstractmethod
    def scrape(self, url: str) -> ScrapedJob: ...


def detect_source(url: str) -> str:
    if re.search(r"boards\.greenhouse\.io|job-boards\.greenhouse\.io", url):
        return "greenhouse"
    if re.search(r"apply\.workable\.com|jobs\.workable\.com", url):
        return "workable"
    if re.search(r"myworkdayjobs\.com|workday\.com", url):
        return "workday"
    if re.search(r"linkedin\.com", url):
        return "linkedin"
    if re.search(r"comeet\.com", url):
        return "comeet"
    if re.search(r"machinelearning\.co\.il", url):
        return "mlisrael"
    return "generic"


def scrape_url(url: str) -> ScrapedJob:
    from src.scrapers.greenhouse import GreenhouseScraper
    from src.scrapers.workable import WorkableScraper
    from src.scrapers.workday import WorkdayScraper
    from src.scrapers.linkedin import LinkedInScraper
    from src.scrapers.comeet import ComeetScraper
    from src.scrapers.generic import GenericScraper
    from src.scrapers.mlisrael import MLIsraelScraper

    source = detect_source(url)

    scraper_map = {
        "greenhouse": GreenhouseScraper,
        "workable":   WorkableScraper,
        "workday":    WorkdayScraper,
        "linkedin":   LinkedInScraper,
        "comeet":     ComeetScraper,
        "mlisrael":   MLIsraelScraper,
        "generic":    GenericScraper,
    }
    scraper_cls = scraper_map.get(source, GenericScraper)
    job = scraper_cls().scrape(url)
    job.source = source
    return job
