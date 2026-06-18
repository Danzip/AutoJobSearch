"""
LinkedIn job discovery via JobSpy (python-jobspy package).
Returns URL+metadata dicts for the batch_search scrape queue.
Descriptions are NOT included here — they're fetched by LinkedInScraper.
"""


def search_linkedin_jobs(
    keywords: str,
    location: str = "Israel",
    results_wanted: int = 25,
    hours_old: int = 168,
) -> list[dict]:
    """
    Use JobSpy to find LinkedIn job URLs.
    Returns list of {url, title, company, board, posted_date} dicts.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("  [LinkedIn direct] python-jobspy not installed, skipping")
        return []

    try:
        import logging
        logging.getLogger("JobSpy").setLevel(logging.WARNING)
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term=keywords,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            description_format="markdown",
            verbose=0,
        )
    except Exception as exc:
        print(f"  [LinkedIn direct] JobSpy error: {exc}")
        return []

    results = []
    for _, row in jobs.iterrows():
        url = str(row.get("job_url") or "")
        if not url or "://www.linkedin.com" not in url and "://linkedin.com" not in url:
            continue
        posted_date = ""
        if row.get("date_posted") is not None:
            try:
                posted_date = str(row["date_posted"])[:10]
            except Exception:
                pass
        results.append({
            "url": url,
            "title": str(row.get("title") or ""),
            "company": str(row.get("company") or ""),
            "board": "LinkedIn",
            "posted_date": posted_date,
        })
    return results
