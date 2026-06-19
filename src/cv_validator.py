"""
Sanity checks for generated CV content: catches a generated cv.md silently
dropping an entire employer (leaving an unexplained employment gap) or
failing to surface a JD-required skill the candidate actually has.
"""

REQUIRED_EMPLOYERS = {
    "Gentex": ["gentex", "guardian optical"],
    "Razor Labs": ["razor labs", "axon vision"],
    "Independent Research": ["independent research"],
}


def missing_employers(cv_text: str) -> list[str]:
    """Return the names of any required employer not mentioned in cv_text."""
    text_lower = cv_text.lower()
    return [
        name
        for name, aliases in REQUIRED_EMPLOYERS.items()
        if not any(alias in text_lower for alias in aliases)
    ]


def missing_required_skills(cv_text: str, requirements: dict) -> list[str]:
    """
    Return required_skills from the job requirements that don't appear anywhere
    in cv_text. Case-insensitive substring match - a rough smoke check, not a
    guarantee of true coverage (e.g. paraphrased skills won't be caught).
    """
    text_lower = cv_text.lower()
    return [
        skill
        for skill in requirements.get("required_skills", [])
        if skill.lower() not in text_lower
    ]
