"""
Direct Comeet company page search for configured Israeli companies.
Bypasses DuckDuckGo entirely — scrapes current openings from each company page.

Returns same dict shape as job_search_workday: {board, title, company, url, description, posted_date}
"""
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "comeet_companies.yaml"


def _load_companies() -> list[dict]:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f).get("companies", [])


def search_comeet_companies(keywords: str = "") -> list[dict]:
    """Scrape current openings from all configured Comeet companies."""
    from src.scrapers.comeet import scrape_company_page

    companies = _load_companies()
    results = []
    kw_lower = keywords.lower() if keywords else ""

    for company in companies:
        try:
            jobs = scrape_company_page(company["slug"])
            matched = []
            for j in jobs:
                # If keywords given, filter by title relevance
                if kw_lower and not any(
                    w in j["title"].lower()
                    for w in kw_lower.split()
                    if len(w) > 3
                ):
                    continue
                matched.append({
                    "board": "Comeet",
                    "title": j["title"],
                    "company": company["name"],
                    "url": j["url"],
                    "description": "",   # fetched later by scrape_url
                    "posted_date": "",
                })
            print(f"  Comeet/{company['name']}: {len(matched)} jobs (of {len(jobs)} total)")
            results.extend(matched)
        except Exception as e:
            print(f"  Comeet/{company['name']}: ERROR {e}")

    return results
