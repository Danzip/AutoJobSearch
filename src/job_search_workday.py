"""
Direct Workday API search for specific Israeli companies.
Bypasses DuckDuckGo and JS rendering entirely.

Returns the same {title, url, board, company, description} dicts as the
DuckDuckGo scrape flow, but with the description already fetched.
"""
import re
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
_CONFIG_PATH = Path(__file__).parent.parent / "config" / "workday_companies.yaml"
_MIN_DESC_CHARS = 200


def _load_companies() -> list[dict]:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f).get("companies", [])


def _api_base(company: dict) -> str:
    sub = company["subdomain"]
    slug = sub.split(".")[0]
    board = company["board"]
    return f"https://{sub}.myworkdayjobs.com/wday/cxs/{slug}/{board}"


def _html_to_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator="\n").strip()


def _public_url(company: dict, path: str) -> str:
    sub = company["subdomain"]
    board = company["board"]
    return f"https://{sub}.myworkdayjobs.com/en-US/{board}{path}"


def _search_company(company: dict, keywords: str, max_results: int) -> list[dict]:
    base = _api_base(company)

    location_ids = company.get("location_ids", [])
    text_search = keywords
    extra = company.get("text_search", "")
    if extra:
        text_search = f"{keywords} {extra}".strip()
    extra_kw = company.get("keywords", "")
    if extra_kw:
        text_search = f"{text_search} {extra_kw}".strip()

    payload = {
        "appliedFacets": {"locations": location_ids} if location_ids else {},
        "limit": max_results,
        "offset": 0,
        "searchText": text_search,
    }

    try:
        r = requests.post(f"{base}/jobs", headers=_HEADERS, json=payload, timeout=12)
        if r.status_code != 200:
            return []
        postings = r.json().get("jobPostings", [])
    except Exception:
        return []

    results = []
    for job in postings:
        path = job.get("externalPath", "")
        if not path:
            continue

        # Fetch full description
        try:
            dr = requests.get(f"{base}{path}", headers=_HEADERS, timeout=12)
            if dr.status_code != 200:
                continue
            info = dr.json().get("jobPostingInfo", {})
            desc = _html_to_text(info.get("jobDescription", ""))
            if len(desc) < _MIN_DESC_CHARS:
                continue
            from src.scrapers.date_utils import parse_relative_date
            results.append({
                "board": "Workday",
                "title": info.get("title") or job.get("title", ""),
                "company": company["name"],
                "url": _public_url(company, path),
                "description": desc,
                "posted_date": parse_relative_date(job.get("postedOn", "")),
            })
        except Exception:
            continue

    return results


def search_workday_companies(keywords: str, max_per_company: int = 10) -> list[dict]:
    """Search all configured Workday companies for Israel CV jobs."""
    companies = _load_companies()
    results = []
    for company in companies:
        hits = _search_company(company, keywords, max_per_company)
        print(f"  Workday/{company['name']}: {len(hits)} jobs")
        results.extend(hits)
    return results
