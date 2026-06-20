from typing import Optional

from src.llm import LLMProvider
from src.prompts import comprehensive_cv_prompt, compress_and_package_prompt, get_generator_system
from src.utils import extract_json_from_text, load_profile_notes


def generate_application_content(
    job: dict,
    requirements: dict,
    profile: dict,
    cv_angle: str,
    llm: LLMProvider,
    reviewer_llm: Optional[LLMProvider] = None,
) -> dict:
    notes = load_profile_notes()
    full_profile = {**profile}
    if notes:
        full_profile["_extra_notes"] = notes

    system = get_generator_system()

    # Pass 1: comprehensive draft - all stories, no bullet limit
    raw1 = llm.complete(
        comprehensive_cv_prompt(job, requirements, full_profile, cv_angle),
        system=system,
        call_type="generate",
    )
    data1 = extract_json_from_text(raw1)
    comprehensive_draft = data1.get("cv_draft_comprehensive", "")

    if not comprehensive_draft:
        print("  WARN  Pass 1 returned empty draft; generation may be degraded")

    # Pass 2: compress to 1 dense page + generate full package
    raw2 = llm.complete(
        compress_and_package_prompt(job, requirements, comprehensive_draft, cv_angle),
        system=system,
        call_type="generate",
    )
    data2 = extract_json_from_text(raw2)

    cv_draft = data2.get("cv_draft_markdown", "")

    if reviewer_llm and cv_draft:
        from src.reviewer import review_cv
        cv_draft = review_cv(job.get("description", ""), cv_draft, reviewer_llm)

    content = {
        "cv_draft_markdown": cv_draft,
        "cover_letter":      data2.get("cover_letter", ""),
        "linkedin_message":  data2.get("linkedin_message", ""),
        "recruiter_email":   data2.get("recruiter_email", ""),
        "talking_points":    data2.get("talking_points", []),
    }
    _fix_em_dashes(content)
    _warn_missing_employers(content)
    return content


def _warn_missing_employers(content: dict) -> None:
    """Warn if the generated CV silently dropped an entire employer (an unexplained gap)."""
    from src.cv_validator import missing_employers
    cv_draft = content.get("cv_draft_markdown", "")
    if not cv_draft:
        return
    missing = missing_employers(cv_draft)
    if missing:
        print(f"  WARN  CV is missing employer(s), leaving an unexplained gap: {', '.join(missing)}")


def _fix_em_dashes(content: dict) -> None:
    """Replace em dashes (—) with plain hyphens in all text fields. Warns if found."""
    fields = ["cv_draft_markdown", "cover_letter", "linkedin_message", "recruiter_email"]
    found = []
    for field in fields:
        val = content.get(field, "")
        if "—" in val:
            found.append(field)
            content[field] = val.replace("—", "-")
    if found:
        print(f"  WARN  em dashes found and replaced in: {', '.join(found)}")
