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


def search_comeet_companies(keywords: str = "", workers: int = 6) -> list[dict]:
    """Scrape current openings from all configured Comeet companies in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.scrapers.comeet import scrape_company_page

    companies = _load_companies()
    kw_lower = keywords.lower() if keywords else ""

    def _scrape_one(company: dict):
        jobs = scrape_company_page(company["slug"])
        matched = []
        for j in jobs:
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
                "description": "",
                "posted_date": "",
            })
        return company["name"], len(jobs), matched

    # Scrape all company pages in parallel; collect into ordered map
    results_map: dict[str, tuple] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_company = {executor.submit(_scrape_one, c): c for c in companies}
        for future in as_completed(future_to_company):
            company = future_to_company[future]
            try:
                name, total, matched = future.result()
                results_map[name] = (total, matched)
            except Exception as e:
                results_map[company["name"]] = (0, [])
                print(f"  Comeet/{company['name']}: ERROR {e}")

    # Print in original company order, collect results
    results = []
    for company in companies:
        total, matched = results_map.get(company["name"], (0, []))
        print(f"  Comeet/{company['name']}: {len(matched)} jobs (of {total} total)")
        results.extend(matched)
    return results
