from typing import Optional

SEARCH_TEMPLATES: dict[str, str] = {
    "Workday":    "site:myworkdayjobs.com {keywords}",
    "Workable":   'site:apply.workable.com "{keywords}" "Israel"',
    "Greenhouse": 'site:job-boards.greenhouse.io "Tel Aviv" "{keywords}"',
    "LinkedIn":   'site:il.linkedin.com/jobs/view "{keywords}" "Israel"',
}

ALL_BOARDS = list(SEARCH_TEMPLATES.keys())


def search_jobs(
    keywords: str,
    boards: Optional[list[str]] = None,
    max_results: int = 10,
) -> list[dict]:
    """
    Search multiple job boards via DuckDuckGo site: queries.
    Returns list of {title, url, snippet, board}.
    """
    from ddgs import DDGS

    if boards is None:
        boards = ALL_BOARDS

    results = []
    with DDGS() as ddg:
        for board in boards:
            if board not in SEARCH_TEMPLATES:
                continue
            query = SEARCH_TEMPLATES[board].format(keywords=keywords)
            try:
                hits = list(ddg.text(query, max_results=max_results))
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
