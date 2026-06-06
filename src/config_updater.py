"""
Auto-generates config.yaml scoring section from the candidate profile.

Run after updating candidate_profile.yaml:
    python -c "from src.config_updater import sync_scoring_config; sync_scoring_config()"

Also called automatically at the start of batch_search.py.
"""
import json
import re
import yaml
from pathlib import Path
from typing import Optional

from src.utils import CONFIG_PATH

_SYSTEM = (
    "You are a scoring configuration generator for a job matching system. "
    "Given a candidate's profile, output JSON config that identifies the best job matches for them. "
    "Return ONLY valid JSON. No markdown code fences, no preamble, no trailing text."
)

_PROMPT_TEMPLATE = """Design a job-match scoring configuration for this candidate.

CANDIDATE PROFILE:
Name: {name}
Education: {education}
Years experience: {years_experience}
Primary skills: {skills}
Hard limits (candidate cannot claim these): {hard_limits}

Story headlines (candidate's actual experience):
{story_headlines}

Return JSON with exactly these fields:
{{
  "dimensions": [
    {{
      "key": "snake_case_key",
      "label": "Human readable label",
      "max_pts": 15,
      "description": "10=this signal is core to the role, 5=mentioned, 0=not relevant"
    }}
  ],
  "excluded_domains": ["domain1", "domain2"],
  "primary_keys": ["key1", "key2"],
  "candidate_degree": "bsc|msc|phd"
}}

Rules:
- max_pts across all dimensions must sum to exactly 85 (seniority covers the remaining 15 out of 100)
- excluded_domains: snake_case domain tags that are clearly outside the candidate's expertise
- primary_keys: 1-2 dimension keys that are the strongest signals; jobs with all of these at 0 get -10pt
- candidate_degree: "bsc" if bachelor's, "msc" if master's, "phd" if doctorate - derive from education field
- Aim for 5-8 dimensions
- Keys must be simple snake_case"""


def _degree_from_profile(profile: dict) -> str:
    """Derive bsc/msc/phd from the profile's education.degree field."""
    edu = profile.get("personal", {}).get("education", {})
    degree_str = edu.get("degree", "").lower()
    if any(x in degree_str for x in ("ph.d", "phd", "doctorate", "doctor")):
        return "phd"
    if any(x in degree_str for x in ("m.sc", "msc", "m.s.", "master", "m.eng")):
        return "msc"
    return "bsc"


def suggest_scoring_config(profile: dict, llm) -> dict:
    """Ask the LLM to suggest scoring dimensions from the candidate's profile."""
    personal = profile.get("personal", {})
    edu = personal.get("education", {})
    skills = profile.get("skills", {})
    stories = profile.get("stories", [])

    prompt = _PROMPT_TEMPLATE.format(
        name=personal.get("name", "Candidate"),
        education=f"{edu.get('degree', 'unknown')} from {edu.get('institution', 'unknown')}",
        years_experience=personal.get("years_experience", "unknown"),
        skills=", ".join(str(s) for s in skills.get("primary", [])[:10]),
        hard_limits=", ".join(str(h) for h in profile.get("hard_limits", [])[:10]),
        story_headlines="\n".join(f"- {s.get('headline', '')}" for s in stories[:15]),
    )

    raw = llm.complete(prompt, _SYSTEM, "config_update")
    raw = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    result = json.loads(raw)

    if "candidate_degree" not in result:
        result["candidate_degree"] = _degree_from_profile(profile)

    return result


def apply_scoring_config(scoring_cfg: dict, config_path: Optional[Path] = None) -> None:
    """Merge scoring_cfg into config.yaml, preserving all other sections."""
    if config_path is None:
        config_path = CONFIG_PATH

    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}

    scoring = cfg.setdefault("scoring", {})
    scoring["dimensions"] = scoring_cfg["dimensions"]
    scoring["excluded_domains"] = scoring_cfg.get("excluded_domains", [])
    scoring["primary_keys"] = scoring_cfg.get("primary_keys", [])
    scoring["candidate_degree"] = scoring_cfg.get("candidate_degree", "bsc")
    scoring.setdefault("threshold", 60)

    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def sync_scoring_config(llm=None) -> None:
    """Read profile, call LLM, write config.yaml scoring section. Called from batch_search.py."""
    from src.utils import load_profile

    if llm is None:
        from src.llm import AnthropicProvider
        from src.utils import load_config
        model = load_config().get("llm", {}).get("analyze_model", "claude-haiku-4-5-20251001")
        llm = AnthropicProvider(model=model)

    profile = load_profile()
    print("Syncing scoring config from candidate profile...")
    suggestions = suggest_scoring_config(profile, llm)
    apply_scoring_config(suggestions)

    dims = suggestions.get("dimensions", [])
    total_pts = sum(d["max_pts"] for d in dims)
    print(f"  Degree:    {suggestions.get('candidate_degree', '?')}")
    print(f"  Dims:      {len(dims)} ({total_pts} pts + 15 seniority = {total_pts + 15} total)")
    print(f"  Excluded:  {suggestions.get('excluded_domains', [])}")
    print(f"  Primary:   {suggestions.get('primary_keys', [])}")
    print("  config.yaml scoring updated.")
