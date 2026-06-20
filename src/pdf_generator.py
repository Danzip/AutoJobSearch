"""
Renders the actual generated CV (the same markdown written to cv.md) to a styled,
one-page PDF via markdown -> HTML -> weasyprint.
PyMuPDF (fitz) is used for page-count verification after rendering.
"""

import re
from pathlib import Path


# Progressive CSS overrides to shrink content onto one page.
# Level 0 = no change; level 1+ progressively reduce margins and font sizes.
_CSS_SHRINK_OVERRIDES = [
    "",
    "@page { margin: 1.2cm 1.4cm 1.0cm 1.4cm; } body { font-size: 9.1pt; } li { font-size: 8.8pt; margin-bottom: 3px; } h1 { font-size: 20pt; }",
    "@page { margin: 1.0cm 1.2cm 0.8cm 1.2cm; } body { font-size: 8.7pt; } li { font-size: 8.4pt; margin-bottom: 2px; } h1 { font-size: 19pt; }",
    "@page { margin: 0.8cm 1.0cm 0.6cm 1.0cm; } body { font-size: 8.3pt; } li { font-size: 8.0pt; margin-bottom: 1px; } h1 { font-size: 18pt; }",
]


_CV_CSS = """
@page {
    size: A4;
    margin: 1.6cm 1.8cm 1.4cm 1.8cm;
}

body {
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 9.7pt;
    line-height: 1.4;
    color: #1a1a1a;
    margin: 0;
}

/* Name - large and prominent */
h1 {
    font-size: 22pt;
    font-weight: bold;
    letter-spacing: -0.5px;
    margin: 0 0 2px 0;
    color: #111;
}

/* Subtitle (role title line immediately after name) */
h1 + p {
    font-size: 10pt;
    color: #444;
    margin: 0 0 2px 0;
    font-weight: normal;
}

/* Contact line (second paragraph after name) */
h1 + p + p {
    font-size: 8.5pt;
    color: #555;
    margin: 0 0 8px 0;
    text-align: center;
}

/* Section headers - dark navy with prominent underline */
h2 {
    font-size: 9pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #1a3055;
    border-bottom: 1.5px solid #1a3055;
    margin: 10px 0 4px 0;
    padding-bottom: 2px;
}

/* h3 fallback for older cv.md files that use ### for role headers */
h3 {
    font-size: 9.7pt;
    font-weight: bold;
    margin: 5px 0 1px 0;
    color: #111;
}

p {
    margin: 2px 0 4px 0;
}

ul {
    margin: 1px 0 5px 0;
    padding-left: 14px;
}
li {
    margin-bottom: 5px;
    font-size: 9.2pt;
}
/* Loose-list items (blank line between bullets in source markdown) wrap content in <p>.
   Reset p margin here so the li margin-bottom is the only spacer — no double-gap. */
li > p {
    margin: 0;
}

strong { font-weight: 700; }
hr { display: none; }
"""


def _count_pdf_pages(pdf_path: Path) -> int:
    """Return the number of pages in a PDF using PyMuPDF."""
    import fitz
    with fitz.open(str(pdf_path)) as doc:
        return len(doc)


def _extract_cv_section(cv_md_text: str) -> str:
    """
    Pull the actual CV draft out of a cv.md file. Current files written by _write_cv()
    have a "# CV Draft - ..." header with Angle/Score metadata, then '---', then the
    real CV; older files have no header and start directly with the real CV. Both
    formats end the CV right before a '## LinkedIn Message' heading.
    """
    cv_part = cv_md_text.split("\n## LinkedIn Message")[0]
    if cv_part.lstrip().startswith("# CV Draft") and "\n---\n" in cv_part:
        cv_part = cv_part.split("\n---\n", 1)[1]
    cv_part = re.sub(r"\n-{3,}\s*$", "", cv_part)
    return cv_part.strip()


def generate_cv_pdf(cv_draft_markdown: str, output_path: Path, max_rounds: int = 3) -> Path:
    """
    Render cv_draft_markdown (the same content saved to cv.md) to a PDF, progressively
    shrinking margins/fonts until it fits on one page.
    """
    import markdown
    from weasyprint import HTML, CSS

    html_body = markdown.markdown(cv_draft_markdown)
    html = f'<html><head><meta charset="utf-8"></head><body>{html_body}</body></html>'

    output_path.parent.mkdir(parents=True, exist_ok=True)
    for level in range(max_rounds + 1):
        shrink_css = _CSS_SHRINK_OVERRIDES[min(level, len(_CSS_SHRINK_OVERRIDES) - 1)]
        stylesheets = [CSS(string=_CV_CSS)]
        if shrink_css:
            stylesheets.append(CSS(string=shrink_css))
        HTML(string=html).write_pdf(str(output_path), stylesheets=stylesheets)
        if _count_pdf_pages(output_path) == 1:
            break
    return output_path


def batch_dir_to_pdf(batch_dir: Path) -> list[Path]:
    """Convert every cv.md under batch_dir to a cv.pdf next to it."""
    generated = []
    for cv_md in sorted(batch_dir.glob("*/cv.md")):
        job_dir = cv_md.parent
        out_pdf = job_dir / "cv.pdf"
        try:
            cv_section = _extract_cv_section(cv_md.read_text())
            generate_cv_pdf(cv_section, out_pdf)
            generated.append(out_pdf)
            print(f"  PDF: {out_pdf.relative_to(batch_dir.parent.parent)}")
        except Exception as e:
            print(f"  FAIL {cv_md}: {e}")
    return generated
