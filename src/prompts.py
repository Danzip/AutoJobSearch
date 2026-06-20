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

ONE PAGE STRICT: The entire CV must fit on one page. 3-4 bullets per role. Each bullet must be 1-2 complete sentences, rich enough to naturally wrap to 2 lines when rendered — do not compress to single-clause fragments. A dense, full-page CV beats a sparse one.

CV FORMAT - use this exact markdown structure (the PDF renderer styles it to match the candidate's reference CV):

# Daniel Ziv
[Role title tailored to this job - plain text, no markdown prefix]
dziv94@gmail.com · +972 54 461 4839 · Tel Aviv · linkedin.com/in/dziv

## SUMMARY
[2-3 sentences tailored to this role. Lead with most relevant experience. No filler.]

## EXPERIENCE

**[Job Title]** · [Company Name], [City]
[Start Year] – [End Year or Present]
- Bullet 1
- Bullet 2
- Bullet 3

## EDUCATION
**B.Sc. Electrical Engineering** · Tel Aviv University · GPA 85 · 2013–2017 | Focus: Computer Vision, Image Processing, Algorithms & Data Structures | Final Project: Pericyte Segmentation: 100/100

## TECHNICAL SKILLS
**[Category]:** item, item, item
**[Category]:** item, item, item

CRITICAL FORMAT RULES:
- h1 line: ONLY "Daniel Ziv" - no role, no dash, just the name
- Line 2: subtitle role title - plain text, no ## or ** prefix
- Line 3: contact info with · (middle dot) NOT | (pipe)
- Section headers (##): ALL CAPS exactly as shown
- Role lines: **Bold Title** · Company, Location (bold title, then middle dot, then company/city)
- Date line: immediately after role line, plain text, format: YYYY – YYYY or YYYY – Present
- Skills section: **Bold Category:** comma-separated items (NO bullet points in skills)
- NEVER use ### (h3 headers) anywhere in the CV
- SKILLS SEPARATION: In the TECHNICAL SKILLS section, add a blank line between each **Category:** line.

WRITING RULES - ABSOLUTE:
- NO em dashes (—) anywhere - use commas, colons, or hyphens
- NO filler: "passionate", "excited", "leveraged", "utilized", "responsible for", "results-driven", "cutting-edge", "innovative"
- NO AI phrasing: "demonstrate", "showcase", "robust" (generic), "diverse experience", "Furthermore", "Additionally"
- NO placeholders: never write [Name], [Company], [Contact], [Role], or any [bracket] text anywhere - every field must be filled with real content or omitted entirely
- NO gap disclosure in the CV: never mention domain mismatches, "adjacent" skills, or missing experience in the summary or bullets. The CV sells what the candidate has. Gap awareness belongs only in talking points.
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


def _build_profile_block(profile: dict) -> str:
    """Shared helper: render profile fields into a prompt-ready string."""
    personal = profile.get("personal", {})
    key_metrics = profile.get("key_metrics", [])
    hard_limits = profile.get("hard_limits", [])
    stories = profile.get("stories", [])
    skills = profile.get("skills", {})

    edu = personal.get("education", {})
    candidate_summary = (
        f"- {personal.get('years_experience', '')}+ years experience\n"
        f"- {edu.get('degree', '')} from {edu.get('institution', '')}\n"
        f"- Location: {personal.get('location', '')}"
    )
    stories_text = "\n\n".join(
        f"[{s['id']}] {s['headline']}\n{s.get('body', '').strip()}"
        for s in stories
    )
    return (
        f"CANDIDATE:\n{candidate_summary}\n\n"
        f"KEY METRICS (exact numbers - never round or change):\n" +
        "\n".join(f"- {m}" for m in key_metrics) +
        f"\n\nSTORIES:\n{stories_text}\n\n"
        f"SKILLS: {yaml.dump(skills, default_flow_style=True, allow_unicode=True)}\n"
        f"HARD LIMITS - NEVER CLAIM:\n" +
        "\n".join(f"- {h}" for h in hard_limits)
    )


def comprehensive_cv_prompt(job: dict, requirements: dict, profile: dict, cv_angle: str) -> str:
    """Pass 1: Dump ALL relevant stories into a comprehensive draft. No page limit."""
    jd = job.get("description", "")[:4000]
    profile_block = _build_profile_block(profile)

    return f"""COMPREHENSIVE CV DRAFT - PASS 1 (no page limit)

{profile_block}

TARGET JOB:
Company: {job.get('company', 'Unknown')}
Title: {job.get('title', 'Unknown')}
Location: {job.get('location', '')}
Required skills: {', '.join(requirements.get('required_skills', []))}
Domains: {', '.join(requirements.get('domains', []))}
Seniority: {requirements.get('seniority', 'unknown')}

CV ANGLE: {cv_angle}

JOB DESCRIPTION:
{jd}

TASK: Write a comprehensive CV that covers every relevant story. Do NOT limit yourself - length is not a concern here. This draft will be compressed to one page in the next pass.

1. Go through every required skill in the JD one by one. For each, find a matching story and plan to include it.
2. Write 4-6 bullets per role. Include every story that has any relevance to this JD.
3. Use the correct markdown structure (# name, plain subtitle, contact with ·, ## CAPS section headers, **Role** · Company date-on-next-line format, **Category:** skills).
4. SKILLS SEPARATION: In TECHNICAL SKILLS, add a blank line between each **Category:** line.

Do not pre-censor - include all relevant content. The compression pass will select the strongest bullets.

Return ONLY valid JSON:
{{"cv_draft_comprehensive": "full comprehensive CV in correct markdown structure, 4-6 bullets per role"}}"""


def compress_and_package_prompt(job: dict, requirements: dict, comprehensive_draft: str, cv_angle: str) -> str:
    """Pass 2: Compress comprehensive draft to 1 dense page and generate full application package."""
    jd = job.get("description", "")[:3000]

    return f"""COMPRESS TO ONE DENSE PAGE + GENERATE FULL APPLICATION PACKAGE

JOB: {job.get('title', '')} at {job.get('company', '')}
CV ANGLE: {cv_angle}

JOB DESCRIPTION (for keyword matching):
{jd}

COMPREHENSIVE CV DRAFT:
{comprehensive_draft}

TASK 1 - COMPRESS:
From the draft above, select 3-4 bullets per role.
- Prioritize: exact metrics, production impact, JD keyword coverage
- BULLET DEPTH: Preserve the full depth of each selected bullet — 1-2 complete sentences that naturally wrap to 2 lines. Do NOT shorten bullets into single-clause fragments. A bullet like "Built X using Y: achieved Z metric; also did W" is correct. A one-liner fragment is not.
- The final page must be DENSE - aim to fill 90%+ of the space, no white space at the bottom
- Keep ALL sections: SUMMARY, every EXPERIENCE role, EDUCATION, TECHNICAL SKILLS
- Preserve the exact markdown structure: # name / plain subtitle / contact with · / ## CAPS headers / **Role** · Company / plain date line / **Category:** skills
- No em dashes, no bracket placeholders
- SKILLS SEPARATION: In TECHNICAL SKILLS, add a blank line between each **Category:** line so each appears on its own line.

TASK 2 - APPLICATION MATERIALS:
Generate the rest of the package based on the compressed CV.

Return ONLY valid JSON:
{{
    "cv_draft_markdown": "compressed one-page CV in correct markdown structure",
    "cover_letter": "4 paragraphs ~280 words. Para 1: specific hook (not generic enthusiasm). Para 2: strongest achievement with exact metric. Para 3: second achievement and why it matters. Para 4: what candidate brings + call to action. No em dashes.",
    "linkedin_message": "3-4 sentences. Casual but professional. One concrete technical fact. No em dashes. Under 300 chars ideally.",
    "recruiter_email": "Start with 'Subject: ...' then blank line then 4-5 sentence body. Professional but direct. No em dashes.",
    "talking_points": ["strongest story mapped to this role's top requirement", "second strongest mapping", "how to handle the biggest gap", "non-obvious domain connection", "good question to ask the interviewer"]
}}"""
