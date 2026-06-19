import json
from typing import Optional

from src.llm import LLMProvider
from src.prompts import generator_prompt, get_generator_system
from src.utils import extract_json_from_text, load_config, load_profile_notes


def _select_stories(stories: list, requirements: dict, max_stories: int) -> list:
    """Pick the most relevant stories by tag overlap with job domains and skills."""
    domains = {d.lower().replace(" ", "_").replace("-", "_")
               for d in requirements.get("domains", [])}
    skills  = {s.lower() for s in requirements.get("required_skills", [])}

    def relevance(story):
        tags = {t.lower() for t in story.get("tags", [])}
        # Direct domain/tag overlap
        score = len(tags & domains) * 2
        # Skill keyword overlap (partial match)
        score += sum(1 for tag in tags
                     for skill in skills
                     if skill in tag or tag in skill)
        # Boost production/edge stories for high production/edge relevance
        if requirements.get("production_relevance", 0) >= 6 and "production" in tags:
            score += 2
        if requirements.get("edge_ai_relevance", 0) >= 6 and "edge_ai" in tags:
            score += 2
        return score

    ranked = sorted(stories, key=relevance, reverse=True)
    return ranked[:max_stories]


def generate_application_content(
    job: dict,
    requirements: dict,
    profile: dict,
    cv_angle: str,
    llm: LLMProvider,
    reviewer_llm: Optional[LLMProvider] = None,
) -> dict:
    cfg = load_config()
    max_stories = cfg.get("llm", {}).get("max_stories_in_prompt", 6)

    # Select only the most relevant stories instead of sending all ~18
    all_stories = profile.get("stories", [])
    selected_stories = _select_stories(all_stories, requirements, max_stories)

    # Build a trimmed copy of the profile for the prompt
    trimmed_profile = {**profile, "stories": selected_stories}

    notes = load_profile_notes()
    if notes:
        trimmed_profile["_extra_notes"] = notes

    prompt = generator_prompt(job, requirements, trimmed_profile, cv_angle)
    raw = llm.complete(prompt, system=get_generator_system(), call_type="generate")
    data = extract_json_from_text(raw)

    cv_draft = data.get("cv_draft_markdown", "")

    if reviewer_llm and cv_draft:
        from src.reviewer import review_cv
        cv_draft = review_cv(job.get("description", ""), cv_draft, reviewer_llm)

    content = {
        "cv_draft_markdown": cv_draft,
        "cover_letter":      data.get("cover_letter", ""),
        "linkedin_message":  data.get("linkedin_message", ""),
        "recruiter_email":   data.get("recruiter_email", ""),
        "talking_points":    data.get("talking_points", []),
    }
    _fix_em_dashes(content)
    return content


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
