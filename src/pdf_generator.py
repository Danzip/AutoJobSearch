"""
Generates a formatted 1-page CV PDF from cv.md tailored highlights + candidate profile.
Uses weasyprint (HTML -> PDF) for clean, styled output.
PyMuPDF (fitz) is used for page-count verification after rendering.
"""

import re
from pathlib import Path


# Progressive CSS overrides to shrink content onto one page.
# Level 0 = no change; level 1+ progressively reduce margins and font sizes.
_CSS_SHRINK_OVERRIDES = [
    "",
    "@page { margin: 1.5cm 1.7cm 1.2cm 1.7cm; } body { font-size: 9.1pt; } li { font-size: 8.7pt; }",
    "@page { margin: 1.2cm 1.4cm 1.0cm 1.4cm; } body { font-size: 8.7pt; } li { font-size: 8.3pt; }",
    "@page { margin: 1.0cm 1.2cm 0.8cm 1.2cm; } body { font-size: 8.3pt; } li { font-size: 8.0pt; }",
]


_CV_CSS = """
@page {
    size: A4;
    margin: 1.8cm 2cm 1.5cm 2cm;
}

* { box-sizing: border-box; }

body {
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: #1a1a1a;
    margin: 0;
}

/* ---- Header ---- */
.header {
    border-bottom: 2px solid #2c2c2c;
    padding-bottom: 6px;
    margin-bottom: 10px;
}
.name {
    font-size: 17pt;
    font-weight: bold;
    letter-spacing: -0.3px;
    margin: 0 0 2px 0;
}
.title-line {
    font-size: 9.5pt;
    color: #444;
    margin: 0 0 3px 0;
}
.contact {
    font-size: 8.5pt;
    color: #555;
}
.contact a { color: #555; text-decoration: none; }

/* ---- Section headings ---- */
h2 {
    font-size: 9pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #2c2c2c;
    margin: 10px 0 4px 0;
    border-bottom: 0.75px solid #ccc;
    padding-bottom: 2px;
}

/* ---- Experience blocks ---- */
.job-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 1px;
}
.job-company { font-weight: bold; font-size: 9.5pt; }
.job-period  { font-size: 8.5pt; color: #555; }
.job-role    { font-style: italic; font-size: 9pt; color: #444; margin-bottom: 3px; }

ul {
    margin: 2px 0 6px 0;
    padding-left: 14px;
}
li {
    margin-bottom: 2px;
    font-size: 9pt;
}
li strong { font-weight: 600; }

/* ---- Education & Skills ---- */
.edu-line  { margin: 2px 0; font-size: 9pt; }
.skills-block { font-size: 9pt; margin-top: 3px; }
.skills-block span { color: #555; }
"""


def _score_bullet(bullet: str, keywords: list[str]) -> int:
    """Count how many JD keywords appear (case-insensitive) in this bullet."""
    bullet_lower = bullet.lower()
    return sum(1 for kw in keywords if kw.lower() in bullet_lower)


def _cut_weakest_bullet(bullets: list[str], keywords: list[str]) -> list[str]:
    """Remove the bullet with the fewest JD keyword matches. Ties go to the last bullet."""
    if len(bullets) <= 1:
        return list(bullets)
    scores = [_score_bullet(b, keywords) for b in bullets]
    # Find last index with minimum score (so ties remove the last bullet)
    min_score = min(scores)
    weakest_idx = max(i for i, s in enumerate(scores) if s == min_score)
    return [b for i, b in enumerate(bullets) if i != weakest_idx]


def _count_pdf_pages(pdf_path: Path) -> int:
    """Return the number of pages in a PDF using PyMuPDF."""
    import fitz
    with fitz.open(str(pdf_path)) as doc:
        return len(doc)


def _extract_tailored_bullets(cv_markdown: str) -> list[str]:
    """Pull the bullet points from the Tailored Highlights section of cv.md."""
    section = re.search(
        r"## Tailored Highlights\s*(.*?)(?=\n## |\Z)",
        cv_markdown,
        re.DOTALL,
    )
    if not section:
        return []
    bullets = []
    for line in section.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            bullets.append(line[2:])
    return bullets


def _md_inline(text: str) -> str:
    """Convert **bold** and `code` in a line to HTML."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def generate_cv_pdf(
    cv_markdown_path: Path,
    profile: dict,
    output_path: Path,
    job_title: str = "",
    company: str = "",
    shrink_level: int = 0,
    bullet_override: list[str] | None = None,
) -> Path:
    """
    Build a properly formatted 1-page CV PDF.
    Tailored highlights come from cv.md; base experience, education, and skills
    come from the profile.
    """
    from weasyprint import HTML, CSS

    cv_text = cv_markdown_path.read_text()
    bullets = bullet_override if bullet_override is not None else _extract_tailored_bullets(cv_text)

    # Derive cv_angle from file header
    angle_match = re.search(r"\*\*Angle:\*\* (.+)", cv_text)
    angle = angle_match.group(1).strip() if angle_match else ""

    personal = profile.get("personal", {})
    edu = personal.get("education", {})
    skills = profile.get("skills", {})

    # Build tailored experience bullets HTML
    bullets_html = "\n".join(
        f"<li>{_md_inline(b)}</li>" for b in bullets
    )

    # Skills summary - flatten relevant categories, keep it short
    skill_cats = {
        "CV / Perception": skills.get("cv_perception", [])[:6],
        "Deep Learning": skills.get("deep_learning", [])[:5],
        "Edge Deployment": skills.get("edge_deployment", [])[:5],
        "Geometry & Math": skills.get("geometry_math", [])[:4],
    }
    skills_html = " &nbsp;|&nbsp; ".join(
        f"<span><strong>{cat}:</strong> {', '.join(items)}</span>"
        for cat, items in skill_cats.items()
        if items
    )

    for_line = f" | {company}" if company else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"></head>
<body>

<div class="header">
  <p class="name">{personal.get('name', '')}</p>
  <p class="title-line">Senior Computer Vision / Deep Learning Engineer{for_line}</p>
  <p class="contact">
    {personal.get('email','')} &nbsp;&bull;&nbsp;
    {personal.get('phone','')} &nbsp;&bull;&nbsp;
    {personal.get('location','')} &nbsp;&bull;&nbsp;
    {personal.get('linkedin','')}
  </p>
</div>

<h2>Experience</h2>

<div class="job-header">
  <span class="job-company">Gentex / Guardian Optical Technologies</span>
  <span class="job-period">2021 - 2023</span>
</div>
<div class="job-role">Deep Learning &amp; Algorithms Engineer - Ramat Gan, Israel</div>
<ul>
{bullets_html if bullets else "<li>See tailored highlights in accompanying notes.</li>"}
</ul>

<div class="job-header">
  <span class="job-company">Razor Labs / Axon Vision</span>
  <span class="job-period">2017 - 2021</span>
</div>
<div class="job-role">Algorithms Engineer - Israel</div>
<ul>
  <li>Object detection and instance segmentation on high-resolution aerial/drone RGB imagery for defense clients (Mafat-adjacent, Elbit-adjacent) — live video pipeline.</li>
  <li>Self-supervised autoencoder anomaly detection for manufacturing defect inspection (cog defects and diamond grading): trained on normal samples, faults appear as reconstruction residuals.</li>
  <li>Hand-on-wheel detection on fisheye in-cabin camera; co-ported Python algorithm to C++ for production pilot.</li>
  <li>Branch-and-bound resource allocation optimization using OR-Tools and Gurobi: 100x computation speedup vs naive solver (Israel Electric Corporation).</li>
</ul>

<div class="job-header">
  <span class="job-company">Independent Research</span>
  <span class="job-period">2024 - present</span>
</div>
<ul>
  <li>Fine-tuned D-FINE (transformer DETR) on VisDrone aerial dataset: <strong>0.321 AP50:95</strong> at 10M parameters. Full pipeline: ONNX export, INT8 quantization, structured pruning (cliff at 70%). Multi-resolution training 640-1280px, W&B tracking.</li>
  <li>Image registration and blemish detection GUI: ECC, Lucas-Kanade optical flow, RANSAC-based robust alignment.</li>
</ul>

<h2>Education</h2>
<p class="edu-line">
  <strong>{edu.get('degree','B.Sc. Electrical Engineering')}</strong>,
  {edu.get('institution','Tel Aviv University')} -
  GPA {edu.get('gpa', 85)}, {edu.get('years','2013-2017')}
</p>
<p class="edu-line" style="font-size:8.5pt; color:#555;">
  Final project: Pericyte cell binary segmentation from biological microscopy images (MATLAB). Grade 100/100.
</p>

<h2>Skills</h2>
<div class="skills-block">{skills_html}</div>

</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shrink_css = _CSS_SHRINK_OVERRIDES[min(shrink_level, len(_CSS_SHRINK_OVERRIDES) - 1)]
    stylesheets = [CSS(string=_CV_CSS)]
    if shrink_css:
        stylesheets.append(CSS(string=shrink_css))
    HTML(string=html).write_pdf(str(output_path), stylesheets=stylesheets)
    return output_path


def generate_cv_pdf_verified(
    cv_markdown_path: Path,
    profile: dict,
    output_path: Path,
    job_title: str = "",
    company: str = "",
    keywords: list[str] | None = None,
    max_rounds: int = 3,
) -> Path:
    """
    Generate a PDF, then verify it fits on one page.
    If it overflows, cut the weakest bullet (by JD keyword relevance) and
    increase CSS shrink level, repeating up to max_rounds times.
    """
    keywords = keywords or []
    bullets = _extract_tailored_bullets(cv_markdown_path.read_text())
    current_bullets = list(bullets)

    for level in range(max_rounds + 1):
        generate_cv_pdf(
            cv_markdown_path, profile, output_path,
            job_title=job_title, company=company,
            shrink_level=level,
            bullet_override=current_bullets,
        )
        if _count_pdf_pages(output_path) == 1:
            break
        if len(current_bullets) > 3:
            current_bullets = _cut_weakest_bullet(current_bullets, keywords)

    return output_path


def batch_dir_to_pdf(batch_dir: Path, profile: dict) -> list[Path]:
    """Convert all cv.md files in a batch directory to PDFs."""
    generated = []
    for cv_md in sorted(batch_dir.glob("*/cv.md")):
        job_dir = cv_md.parent
        dir_name = job_dir.name  # e.g. 01_Mobileye_DL_RD_Team_Lead
        parts = dir_name.split("_", 2)
        company = parts[1] if len(parts) > 1 else ""
        # Parse company and title from description.md if possible
        desc_md = job_dir / "description.md"
        if desc_md.exists():
            first_line = desc_md.read_text().split("\n")[0].lstrip("# ").strip()
            if " - " in first_line or " - " in first_line:
                c, _, t = first_line.partition(" - ")
                company = c.strip()
        out_pdf = job_dir / "cv.pdf"
        try:
            generate_cv_pdf(cv_md, profile, out_pdf, company=company)
            generated.append(out_pdf)
            print(f"  PDF: {out_pdf.relative_to(batch_dir.parent.parent)}")
        except Exception as e:
            print(f"  FAIL {cv_md}: {e}")
    return generated
