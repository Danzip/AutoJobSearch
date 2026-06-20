#!/usr/bin/env python3
"""Helper: write cv.md and render cv.pdf for one job folder.
Usage: python write_cv.py <folder_name> <angle> <score>
Then paste CV markdown on stdin, end with Ctrl-D.
Or import and call write_job_cv() directly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SCRAPED = Path("outputs/scraped")


def write_job_cv(folder: str, angle: str, score: float, cv_md: str,
                 linkedin: str = "", email: str = "", talking: list = None,
                 company: str = "", title: str = ""):
    job_dir = SCRAPED / folder
    talking = talking or []

    parts = [f"# CV Draft - {company or folder} / {title}\n",
             f"**Angle:** {angle}  \n**Score:** {score:.0f}/100\n\n---\n\n",
             cv_md.strip()]
    if linkedin:
        parts.append(f"\n\n## LinkedIn Message\n\n{linkedin}")
    if email:
        parts.append(f"\n\n## Recruiter Email\n\n{email}")
    if talking:
        parts.append("\n\n## Talking Points\n\n" +
                     "\n".join(f"{i+1}. {p}" for i, p in enumerate(talking)))

    cv_file = job_dir / "cv.md"
    cv_file.write_text("\n".join(parts))

    from src.pdf_generator import generate_cv_pdf, _extract_cv_section
    cv_section = _extract_cv_section(cv_file.read_text())
    generate_cv_pdf(cv_section, job_dir / "cv.pdf")
    print(f"  wrote {cv_file}  +  cv.pdf")
