import re
from pathlib import Path
from typing import Optional


def _parse_linkedin_hit(hit: dict) -> Optional[dict]:
    """Extract name, role, linkedin_url from a raw DuckDuckGo search hit."""
    url = hit.get("href", "") or hit.get("url", "")
    title = hit.get("title", "")

    if "linkedin.com/in/" not in url:
        return None

    # Strip "| LinkedIn" suffix and anything after
    clean = re.sub(r"\s*\|\s*LinkedIn.*$", "", title, flags=re.IGNORECASE).strip()

    if " - " in clean:
        name, _, role_part = clean.partition(" - ")
        # "Senior Engineer at Company Name" → "Senior Engineer"
        role = re.sub(r"\s+at\s+.+$", "", role_part, flags=re.IGNORECASE).strip()
    else:
        name = clean
        role = ""

    if not name or len(name) < 3:
        return None

    return {"name": name.strip(), "role": role.strip(), "linkedin_url": url}


def find_referral_targets(
    company: str,
    location: str = "Israel",
    max_results: int = 5,
) -> list[dict]:
    """Search LinkedIn for employees at company via DuckDuckGo. No login needed."""
    from ddgs import DDGS

    query = f'site:linkedin.com/in "{company}" "{location}"'
    targets = []
    try:
        with DDGS() as ddg:
            hits = list(ddg.text(query, max_results=max_results * 3))
        for hit in hits:
            parsed = _parse_linkedin_hit(hit)
            if parsed:
                targets.append(parsed)
            if len(targets) >= max_results:
                break
    except Exception:
        pass
    return targets


def write_referral_targets_md(job_dir: Path, job: dict, targets: list[dict]) -> Path:
    """Write referral_targets.md into the job directory."""
    company = job.get("company", "")
    title = job.get("title", "")

    if targets:
        targets_md = "\n".join(
            f"- [{t['name']}]({t['linkedin_url']}) — {t['role']}"
            for t in targets
        )
    else:
        targets_md = (
            "_No targets found via automated search. Search manually:_\n\n"
            f'`site:linkedin.com/in "{company}" "Israel"`'
        )

    connection_msg = (
        f"Hi [Name], I came across the {title} role at {company} and I'd love to connect. "
        f"I have X years of experience in [relevant area] and I'm very interested in what "
        f"{company} is building. Would you be open to a quick chat or to pass along my CV?"
    )

    content = f"""# Referral Targets — {company} / {title}

## Potential Contacts

{targets_md}

---

## Connection Message Template

> {connection_msg}

*Edit [Name] and personalize the message before sending. Do NOT send automatically.*
"""
    out_path = job_dir / "referral_targets.md"
    out_path.write_text(content)
    return out_path
