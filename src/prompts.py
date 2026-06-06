import json
import yaml


ANALYZER_SYSTEM = (
    "You are a job requirements extractor. Extract structured information from job descriptions. "
    "Return ONLY valid JSON. No markdown code fences, no preamble, no trailing text."
)


def analyzer_prompt(description: str, dimensions: list[dict] | None = None) -> str:
    """
    Build the analyzer prompt. If dimensions is None, loads from config at call time.
    Passing dimensions explicitly allows tests to inject custom dims without patching.
    """
    if dimensions is None:
        from src.utils import load_config
        cfg = load_config()
        dimensions = cfg.get("scoring", {}).get("dimensions", [])

    # Build relevance fields and scoring guide from config dimensions
    relevance_fields = {d["key"]: 0 for d in dimensions}
    scoring_guide = "\n".join(
        f"- {d['key']}: {d['description']}" for d in dimensions
    )

    schema = {
        "company": "company name or empty string",
        "title": "exact job title",
        "seniority": "one of: junior, mid, senior, lead, principal, staff, unknown",
        "degree_required": "one of: bsc, msc, phd, none",
        "required_skills": ["skill1", "skill2"],
        "nice_to_have_skills": ["skill1"],
        "domains": ["list of domains e.g. computer_vision, deep_learning, nlp, robotics, backend, fullstack, data_science"],
        "reasons_to_apply": ["specific reason"],
        "concerns": ["specific concern"],
        **relevance_fields,
    }

    return f"""Extract requirements from this job description.

JOB DESCRIPTION:
{description}

Return this exact JSON (all relevance fields are integers 0-10):
{json.dumps(schema, indent=4)}

Scoring guide (0-10 integers):
{scoring_guide}"""


GENERATOR_SYSTEM = (
    "You generate tailored job application content based on the candidate's profile. "
    "Rules you must follow:\n"
    "1. Only use facts explicitly present in the candidate's stories - never invent experience\n"
    "2. Use the exact metric numbers provided - never round or change them\n"
    "3. NO EM DASHES anywhere - use commas, colons, or hyphens instead\n"
    "4. Concise, non-AI-sounding language. No filler phrases.\n"
    "5. Never claim skills listed under HARD LIMITS\n"
    "6. Mirror the job description's buzzwords and terminology where they accurately describe the candidate's experience\n"
    "7. CV bullets must fit on ONE PAGE in spirit: max 5-6 tight bullets, no preamble, no padding\n"
    "8. Return ONLY valid JSON - no markdown code fences, no preamble"
)


REVIEWER_SYSTEM = (
    "You are a CV reviewer. "
    "Your job is to improve CV bullets to better match a specific job description. "
    "Return ONLY valid JSON. No markdown code fences, no preamble."
)


def reviewer_prompt(jd: str, cv_draft: str) -> str:
    return f"""Review this CV draft against the job description and improve the bullets.

JOB DESCRIPTION:
{jd}

CV DRAFT:
{cv_draft}

Tasks:
1. Flag JD keywords absent from the CV bullets
2. Flag any bullet the candidate could not clearly explain in an interview
3. Tighten verbose bullets to a single line each

Return this exact JSON:
{{
    "improved_cv": "full improved bullet list as markdown (- bullets), same format as input",
    "flags": ["keyword missing: X", "weak bullet: Y"]
}}"""


def generator_prompt(job: dict, requirements: dict, profile: dict, cv_angle: str) -> str:
    personal = profile.get("personal", {})
    key_metrics = profile.get("key_metrics", [])
    hard_limits = profile.get("hard_limits", [])
    stories = profile.get("stories", [])
    skills = profile.get("skills", {})

    stories_text = "\n\n".join(
        f"[{s['id']}] {s['headline']}\n{s.get('body', '').strip()}"
        for s in stories
    )
    skills_text = yaml.dump(skills, default_flow_style=True, allow_unicode=True)
    hard_limits_text = "\n".join(f"- {h}" for h in hard_limits)
    metrics_text = "\n".join(f"- {m}" for m in key_metrics)

    edu = personal.get("education", {})
    candidate_summary = (
        f"- {personal.get('years_experience', '')}+ years experience\n"
        f"- {edu.get('degree', '')} from {edu.get('institution', '')}\n"
        f"- Location: {personal.get('location', '')}"
    )

    return f"""Generate tailored job application content for {personal.get('name', 'the candidate')}.

CANDIDATE:
{candidate_summary}

KEY METRICS (use these exact numbers - do not round or change):
{metrics_text}

STORIES (use only these, do not invent anything):
{stories_text}

SKILLS: {skills_text}

HARD LIMITS - NEVER CLAIM THESE IN ANY OUTPUT:
{hard_limits_text}

TARGET JOB:
Company: {job.get('company', 'Unknown')}
Title: {job.get('title', 'Unknown')}
Location: {job.get('location', '')}
Required skills: {', '.join(requirements.get('required_skills', []))}
Domains: {', '.join(requirements.get('domains', []))}
Seniority: {requirements.get('seniority', 'unknown')}

CV ANGLE TO EMPHASIZE: {cv_angle}

BUZZWORD RULE: Where the JD uses specific terms and they accurately describe the candidate's
experience, use those exact words. Do not paraphrase away from JD terminology.

Return this exact JSON:
{{
    "cv_draft_markdown": "5-6 tight bullet points. One page in spirit - no preamble, no padding. Mirror JD buzzwords where accurate. Exact metrics. No em dashes. Use '- ' markdown bullets.",
    "cover_letter": "4 paragraphs, ~280 words. Para 1: specific hook - one concrete thing about this company or role that connects to the candidate's background (not generic enthusiasm). Para 2: strongest relevant achievement in narrative form with exact metric. Para 3: second relevant achievement and why it matters here. Para 4: what the candidate would bring to the team + call to action. No em dashes. No filler ('excited to', 'thrilled', 'passionate about'). Professional and direct. Signed with candidate name.",
    "linkedin_message": "3-4 sentences. Casual but professional. Reference specific role and one concrete fact. No em dashes.",
    "recruiter_email": "Start with 'Subject: ...' then blank line then body. 4-5 sentences. Professional but direct. No em dashes.",
    "talking_points": ["specific point from real experience", "point 2", "point 3", "point 4", "point 5"]
}}"""
