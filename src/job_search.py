from typing import Optional

SEARCH_TEMPLATES: dict[str, str] = {
    "Workday":        "site:myworkdayjobs.com {keywords}",
    "Workable":       'site:apply.workable.com "{keywords}" "Israel"',
    "Greenhouse":     'site:job-boards.greenhouse.io "Tel Aviv" "{keywords}"',
    "Comeet":         'site:comeet.com/jobs "{keywords}" "israel"',
    "LinkedIn_jobs":  'site:linkedin.com/jobs/view "{keywords}" "tel aviv"',
    "LinkedIn_posts": 'site:linkedin.com/posts "{keywords}" "hiring" "israel"',
    "ML_Israel":      'site:machinelearning.co.il/job {keywords}',
}

ALL_BOARDS = list(SEARCH_TEMPLATES.keys())

# DDG timelimit options: "d"=day, "w"=week, "m"=month, "y"=year
def _ddg_timelimit(max_days: int) -> Optional[str]:
    if max_days <= 1:
        return "d"
    if max_days <= 7:
        return "w"
    if max_days <= 30:
        return "m"
    if max_days <= 365:
        return "y"
    return None


def search_jobs(
    keywords: str,
    boards: Optional[list[str]] = None,
    max_results: int = 10,
    max_age_days: Optional[int] = None,
) -> list[dict]:
    """
    Search multiple job boards via DuckDuckGo site: queries.
    Returns list of {title, url, snippet, board}.
    max_age_days: if set, restricts DDG results to that time window (rounded up to nearest DDG bucket).
    """
    from ddgs import DDGS
    from src.utils import load_config

    if boards is None:
        boards = ALL_BOARDS

    if max_age_days is None:
        max_age_days = load_config().get("search", {}).get("max_job_age_days", 180)

    timelimit = _ddg_timelimit(max_age_days)

    results = []
    with DDGS() as ddg:
        for board in boards:
            if board not in SEARCH_TEMPLATES:
                continue
            query = SEARCH_TEMPLATES[board].format(keywords=keywords)
            try:
                hits = list(ddg.text(query, max_results=max_results, timelimit=timelimit))
                for h in hits:
                    results.append(
                        {
                            "board": board,
                            "title": h.get("title", ""),
                            "url": h.get("href", ""),
                            "snippet": h.get("body", ""),
                        }
                    )
            except Exception as e:
                results.append(
                    {
                        "board": board,
                        "title": f"[Search error: {e}]",
                        "url": "",
                        "snippet": "",
                    }
                )

    return results
