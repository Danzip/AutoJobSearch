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


GENERATOR_SYSTEM = """You are an ATS optimization specialist and senior engineering hiring manager embedded in an automated job application pipeline.
Maximize interview conversion rate while maintaining full technical credibility.

MASTER RESUME RULES:
- Only use facts from the candidate's stories - never invent skills, projects, metrics, or experience
- Exact metrics only: 0.321 AP50:95, 20 FPS, 80 MB, 100x speedup - never round or change them
- Every bullet must trace to a specific story; every claim must survive a senior technical interview
- Never claim skills in HARD LIMITS

CANDIDATE-SPECIFIC FRAMING (enforce always):
- Head pose = DMS (driver-facing camera) only, NOT full body or CMS
- IMU work = coordinate sync for training labels, NOT VIO or SLAM
- C++ = co-ported with a C++ specialist, NOT independent C++ development
- Razor Labs = Axon Vision (same company, different legal entity)

JD COVERAGE CHECK - do this for every required and important skill in the JD:
1. Search the candidate's stories AND the MASTER STORY REFERENCE for a match
2. If a story covers it: surface it in the CV bullets using the JD's exact terminology
3. If no story but the skill appears in the candidate's skills list: add it to TECHNICAL SKILLS at minimum
4. If neither: leave it out - never invent
The goal is zero uncovered requirements that the candidate actually has. Missing a real match is a failure mode.

ATS & KEYWORD STRATEGY:
- Mirror the JD's exact terminology where it accurately describes the candidate's experience
- Prioritize: production deployment, real-time systems, ownership, quantitative results, optimization
- For CV/DL roles surface: Computer Vision, Deep Learning, PyTorch, OpenCV, ONNX, Edge AI, model compression, anomaly detection, defect inspection, inference optimization
- Every keyword must be defensible in a technical interview - no stuffing

ONE PAGE STRICT: The entire CV must fit on one page. Max 3 bullets per role (4 for the most recent if essential). Cut ruthlessly - a shorter, punchy CV beats a long one every time.

CV FORMAT (match candidate's reference CV structure):
- Name + subtitle + contact header
- SUMMARY: 2-3 sentences tailored to this specific role, lead with most relevant experience
- EXPERIENCE: 3 bullets per role max, most relevant first, one page total
- EDUCATION: degree, institution, GPA, relevant coursework/project
- TECHNICAL SKILLS: categorized (Algorithms, Image Processing, Deep Learning, Data Science, Languages & Tools)

WRITING RULES - ABSOLUTE:
- NO em dashes (—) anywhere - use commas, colons, or hyphens
- NO filler: "passionate", "excited", "leveraged", "utilized", "responsible for", "results-driven", "cutting-edge", "innovative"
- NO AI phrasing: "demonstrate", "showcase", "robust" (generic), "diverse experience", "Furthermore", "Additionally"
- NO placeholders: never write [Name], [Company], [Contact], [Role], or any [bracket] text anywhere - every field must be filled with real content or omitted entirely
- Use direct, engineer-to-engineer language: "Built", "Replaced", "Identified", "Reduced", "Deployed"
- Specific outcomes and exact numbers, not vague improvements
- The final text should sound like a real engineer wrote it for a specific job

INTERVIEW DEFENSIBILITY: For every major claim ask "Could the candidate confidently explain this in a senior technical interview?" If not - weaken, rewrite, or remove.

Return ONLY valid JSON. No markdown code fences, no preamble."""


def get_generator_system() -> str:
    """
    GENERATOR_SYSTEM plus the docx master story reference, combined into one string.
    Anthropic's prompt cache only caches an exact prefix of the `system` block, so the
    (large, identical-across-jobs) docx text must live here rather than in the per-job
    user prompt to actually get cached instead of being billed in full on every call.
    """
    story_reference = _load_story_reference()
    if not story_reference:
        return GENERATOR_SYSTEM
    return f"""{GENERATOR_SYSTEM}

MASTER STORY REFERENCE (from input/*.docx):
This document contains the full narrative, framing notes, and nuances for every story.
Use it as the authoritative source for HOW to frame each experience. The per-job SELECTED STORIES
list below is a structured, pre-filtered summary - this document has the full depth, framing
caveats, and interview defensibility notes.
{story_reference}"""


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


def _load_story_reference() -> str:
    """Load all .docx files from input/. Returns empty string if none found."""
    try:
        from docx import Document
        from pathlib import Path
        input_dir = Path(__file__).parent.parent / "input"
        docx_files = sorted(input_dir.glob("*.docx"))
        if not docx_files:
            return ""
        parts = []
        for path in docx_files:
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            if text:
                parts.append(f"[{path.name}]\n{text}")
        return "\n\n".join(parts)
    except Exception:
        return ""


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

SELECTED STORIES (pre-filtered by relevance to this role):
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

JD COVERAGE - go through each required skill above one by one:
For each item, search the stories and MASTER STORY REFERENCE. If covered: put it in the CV using the JD's exact term.
If not in stories but in skills list: add it to TECHNICAL SKILLS. If neither: skip it.
Do not move on until every required skill has been checked.

CV FORMAT - ONE PAGE STRICT:
Full CV structure: Name + subtitle + contact | SUMMARY (2-3 sentences tailored to this role) |
EXPERIENCE (3 bullets per role max, most relevant first) | EDUCATION | TECHNICAL SKILLS (categorized).
One page total. Cut ruthlessly. No em dashes anywhere.

BUZZWORD RULE: Where the JD uses specific terms and they accurately describe the candidate's
experience, use those exact words. Do not paraphrase away from JD terminology.

Return this exact JSON:
{{
    "cv_draft_markdown": "Full one-page CV in markdown. Sections: name/subtitle/contact header, SUMMARY paragraph, EXPERIENCE (3 bullets per role max), EDUCATION, TECHNICAL SKILLS categories. No em dashes. Exact metrics. JD keywords where accurate.",
    "cover_letter": "4 paragraphs, ~280 words. Para 1: specific hook connecting this company/role to candidate background (not generic enthusiasm). Para 2: strongest relevant achievement with exact metric. Para 3: second achievement and why it matters here. Para 4: what candidate brings + call to action. No em dashes. No filler.",
    "linkedin_message": "3-4 sentences. Casual but professional. Reference specific role and one concrete technical fact. No em dashes.",
    "recruiter_email": "Start with 'Subject: ...' then blank line then body. 4-5 sentences. Professional but direct. No em dashes.",
    "talking_points": ["specific point from real experience", "point 2", "point 3", "point 4", "point 5"]
}}"""
