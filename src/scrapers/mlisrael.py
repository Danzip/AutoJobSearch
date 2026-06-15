import re
import requests
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, ScrapedJob, ScraperError
from src.scrapers.generic import HEADERS, _clean

# Noise lines to drop from description
_NOISE = re.compile(
    r"^(✕|Full Name\*?|Email\*?|Phone(\s*\(optional\))?|Introductory letter|"
    r"Add CV file|Your application was sent|Apply for job|Back to jobs|"
    r"Share this job|Send message|Cookie|Privacy|Terms|Login|Register|Newsletter|"
    r"Machine Learning Israel|MDLI|כל הזכויות|All rights reserved|"
    r"Website$|Hybrid$|Full.?Time$|Remote$|On.?site$)$",
    re.IGNORECASE,
)


class MLIsraelScraper(BaseScraper):
    def scrape(self, url: str) -> ScrapedJob:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ScraperError(f"Failed to fetch {url}: {e}") from e

        soup = BeautifulSoup(resp.text, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        full_text = soup.get_text(separator="\n")

        # Job title: first h1 or h2
        title = ""
        for tag in ("h1", "h2"):
            el = soup.find(tag)
            if el:
                title = el.get_text(strip=True)
                break

        # Location
        location = "Israel"
        loc_match = re.search(
            r"(Tel Aviv|Herzliya|Ramat Gan|Jerusalem|Haifa|Be'er Sheva|Remote|Israel)",
            full_text,
            re.IGNORECASE,
        )
        if loc_match:
            location = loc_match.group(1)

        # Company: appears right before "Website" in the company info block
        company = ""
        company_match = re.search(r"([A-Za-z0-9][^\n]{1,50})\n(?:[^\n]{1,50}\n)?Website", full_text)
        if company_match:
            candidate = company_match.group(1).strip()
            # Reject if it looks like a noise line
            if not _NOISE.match(candidate) and len(candidate) < 60:
                company = candidate

        # Description: strip everything before "Published on" (form + company info)
        pub_match = re.search(r"Published on \d{2}\.\d{2}\.\d{2}", full_text)
        if pub_match:
            desc_raw = full_text[pub_match.end():]
        else:
            desc_raw = full_text

        # Filter noise lines
        lines = []
        for line in desc_raw.splitlines():
            line = line.strip()
            if not line or _NOISE.match(line):
                continue
            lines.append(line)

        description = _clean("\n".join(lines))

        return ScrapedJob(
            title=title,
            company=company,
            location=location,
            description=description,
            source="mlisrael",
        )
