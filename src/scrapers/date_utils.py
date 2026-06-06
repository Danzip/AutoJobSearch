"""Parse relative date strings from job boards into ISO date strings."""
import re
from datetime import datetime, timedelta


def parse_relative_date(text: str) -> str:
    """
    Parse strings like '2 months ago', 'Posted 5 Days Ago', '17 hours ago'.
    Returns ISO date string YYYY-MM-DD, or '' if not parseable.
    """
    text = text.strip().lower()
    now = datetime.now()

    patterns = [
        (r"(\d+)\s*hour",  lambda n: now - timedelta(hours=n)),
        (r"(\d+)\s*day",   lambda n: now - timedelta(days=n)),
        (r"(\d+)\s*week",  lambda n: now - timedelta(weeks=n)),
        (r"(\d+)\s*month", lambda n: now - timedelta(days=n * 30)),
        (r"(\d+)\s*year",  lambda n: now - timedelta(days=n * 365)),
        (r"yesterday",     lambda _: now - timedelta(days=1)),
        (r"today",         lambda _: now),
    ]

    for pattern, calc in patterns:
        m = re.search(pattern, text)
        if m:
            n = int(m.group(1)) if m.lastindex else 0
            return calc(n).strftime("%Y-%m-%d")

    # Try ISO format directly: 2025-04-12T...
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)

    return ""


def is_stale(posted_date: str, max_days: int = 180) -> bool:
    """Return True if posted_date is older than max_days. False if date unknown."""
    if not posted_date:
        return False
    try:
        posted = datetime.strptime(posted_date, "%Y-%m-%d")
        return (datetime.now() - posted).days > max_days
    except ValueError:
        return False
