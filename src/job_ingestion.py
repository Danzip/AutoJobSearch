from src import db
from src.scrapers.base import ScrapedJob


def save_job(
    company: str,
    title: str,
    location: str,
    url: str,
    source: str,
    description: str,
) -> int:
    return db.insert_job(
        {
            "company": company,
            "title": title,
            "location": location,
            "url": url,
            "source": source,
            "raw_description": description,
            "status": "found",
        }
    )


def save_scraped_job(scraped: ScrapedJob, url: str) -> int:
    return save_job(
        company=scraped.company,
        title=scraped.title,
        location=scraped.location,
        url=url,
        source=scraped.source,
        description=scraped.description,
    )
