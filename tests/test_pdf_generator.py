import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pdf_generator import (
    _count_pdf_pages,
    _extract_cv_section,
    _CSS_SHRINK_OVERRIDES,
    _CV_CSS,
    generate_cv_pdf,
)


# ── CSS shrink overrides ───────────────────────────────────────────────────────

def test_shrink_override_level_0_empty():
    assert _CSS_SHRINK_OVERRIDES[0] == ""


def test_shrink_override_level_1_has_smaller_margin():
    override = _CSS_SHRINK_OVERRIDES[1]
    assert "margin" in override or "font-size" in override


def test_shrink_overrides_has_at_least_3_levels():
    assert len(_CSS_SHRINK_OVERRIDES) >= 3


def test_shrink_overrides_reduce_li_margin():
    """Each shrink level should decrease li margin-bottom to reclaim vertical space."""
    import re
    margins = []
    for override in _CSS_SHRINK_OVERRIDES[1:]:
        m = re.search(r"li\s*\{[^}]*margin-bottom:\s*(\d+)px", override)
        if m:
            margins.append(int(m.group(1)))
    assert len(margins) >= 2, "At least 2 shrink levels should set li margin-bottom"
    assert margins == sorted(margins, reverse=True), "li margin-bottom must decrease across shrink levels"


# ── Markdown rendering helpers ─────────────────────────────────────────────────

def _render_md(text: str) -> str:
    import markdown
    return markdown.markdown(text)


# ── Bullet spacing and consistency ────────────────────────────────────────────
# These tests would FAIL on the original code (2px margin, mixed loose/tight rendering).

def test_li_margin_in_range_for_multiline_bullets():
    """li margin-bottom must be 4-9px. Long multi-line bullets provide visual mass;
    too little (<=2px) smushes bullets together, too much (>=10px) creates excessive
    gaps when bullets already wrap to 2 lines.
    FAILS on original 2px (too tight) and on the interim 12px (too loose)."""
    import re
    m = re.search(r"li\s*\{[^}]*margin-bottom:\s*(\d+)px", _CV_CSS)
    assert m, "li { margin-bottom } not found in _CV_CSS"
    value = int(m.group(1))
    assert 4 <= value <= 9, (
        f"li margin-bottom is {value}px — must be 4-9px to work with multi-line bullets"
    )


def test_tight_list_all_bullets_same_element_type():
    """Tight bullets (no blank lines between them) must ALL be bare <li>text</li>.
    If any bullet gets a <p> wrapper (loose-list mixing), font sizes become inconsistent.
    FAILS when blank lines are accidentally inserted between same-role bullets."""
    html = _render_md("- bullet one\n- bullet two\n- bullet three\n")
    assert "<li><p>" not in html, (
        "Tight list has <p>-wrapped items — mixed tight/loose rendering causes inconsistent bullet font sizes"
    )
    assert html.count("<li>") == 3, "Expected exactly 3 <li> elements"


def test_skill_categories_with_blank_lines_render_as_separate_paragraphs():
    """Blank lines between **Category:** skill lines produce separate <p> elements.
    FAILS if blank lines are removed — categories run together with no visual gap."""
    md = "**Computer Vision:** detection, tracking\n\n**Deep Learning:** PyTorch, ONNX\n"
    html = _render_md(md)
    assert html.count("<p>") == 2, (
        f"Expected 2 separate <p> elements for skill categories, got {html.count('<p>')} — "
        "missing blank lines between categories will collapse them into one block"
    )


# ── Page count ─────────────────────────────────────────────────────────────────

def test_count_pdf_pages_real_file(tmp_path):
    try:
        from weasyprint import HTML
        html = "<html><body><p>Hello</p></body></html>"
        pdf_path = tmp_path / "test.pdf"
        HTML(string=html).write_pdf(str(pdf_path))
        assert _count_pdf_pages(pdf_path) == 1
    except ImportError:
        import pytest
        pytest.skip("weasyprint not installed")


def test_count_pdf_pages_missing_file_raises(tmp_path):
    import pytest
    with pytest.raises(Exception):
        _count_pdf_pages(tmp_path / "nonexistent.pdf")


# ── Extract CV section from cv.md ───────────────────────────────────────────────

def test_extract_cv_section_strips_header_in_new_format():
    """Current _write_cv() format: '# CV Draft' header + Angle/Score, then '---', then the real CV."""
    md = """# CV Draft — Acme / Engineer

**Angle:** Edge AI
**Score:** 88/100

---

# Daniel Ziv
The actual CV body, including Razor Labs experience.

---

## LinkedIn Message

Some message here.
"""
    section = _extract_cv_section(md)
    assert section.startswith("# Daniel Ziv")
    assert "Razor Labs" in section
    assert "LinkedIn Message" not in section
    assert "CV Draft" not in section


def test_extract_cv_section_handles_old_format_with_no_header():
    """Older cv.md files have no '# CV Draft' header - the CV starts at line 1."""
    md = """# Daniel Ziv
The actual CV body, including Razor Labs experience.

---

## LinkedIn Message

Some message here.
"""
    section = _extract_cv_section(md)
    assert section.startswith("# Daniel Ziv")
    assert "Razor Labs" in section
    assert "LinkedIn Message" not in section


def test_extract_cv_section_returns_whole_text_when_no_linkedin_section():
    md = "# Daniel Ziv\nNo LinkedIn section here, just the CV.\n"
    assert _extract_cv_section(md) == md.strip()


# ── PDF generation from real markdown ───────────────────────────────────────────

def test_generate_cv_pdf_produces_one_page(tmp_path):
    pytest.importorskip("weasyprint")

    cv_markdown = """# Daniel Ziv
Computer Vision Engineer
dziv94@gmail.com · +972 54 461 4839 · Tel Aviv · linkedin.com/in/dziv

## SUMMARY
Computer vision engineer with experience in real-time detection and tracking.

## EXPERIENCE

**Independent ML Research** · Self-Employed, Tel Aviv
2024 – Present
- Fine-tuned D-FINE on VisDrone: 0.321 AP50:95 at 10M parameters

- Image registration GUI using ECC alignment and RANSAC-based outlier rejection

**Gentex / Guardian Optical Technologies** · Ramat Gan
2021 – 2023
- Replaced U-Net with YOLOv8 on Ambarella CV22S: 2x FPS, 6x compression
- Head pose via PnP solver, gaze tracking, facial landmarks in 50ms latency budget

## EDUCATION
**B.Sc. Electrical Engineering** · Tel Aviv University · GPA 85 · 2013–2017

## TECHNICAL SKILLS
**Computer Vision:** Object detection, tracking, segmentation
**Frameworks:** PyTorch, ONNX, TensorRT
"""
    out_pdf = tmp_path / "cv.pdf"
    result = generate_cv_pdf(cv_markdown, out_pdf)
    assert result == out_pdf
    assert out_pdf.exists()
    assert _count_pdf_pages(out_pdf) == 1


def test_generate_cv_pdf_with_loose_list_produces_one_page(tmp_path):
    """CV using blank-line project separators (loose lists) must still fit one page."""
    pytest.importorskip("weasyprint")

    cv_markdown = """# Daniel Ziv
Computer Vision Engineer
dziv94@gmail.com · +972 54 461 4839 · Tel Aviv · linkedin.com/in/dziv

## SUMMARY
CV engineer with edge AI and production deployment background.

## EXPERIENCE

**Independent ML Research** · Self-Employed, Tel Aviv
2024 – Present
- Fine-tuned D-FINE on VisDrone: 0.321 AP50:95 at 10M parameters; INT8 ONNX export

- Image registration and blemish detection GUI using ECC alignment, RANSAC outlier rejection

**Gentex / Guardian Optical Technologies** · Ramat Gan
2021 – 2023
- Replaced U-Net with YOLOv8 on Ambarella CV22S: 2x FPS (10 to 20), 6x compression (500 to 80 MB)

- Head pose via PnP solver, concurrent gaze and landmark detection in fixed 50ms budget

**Razor Labs / Axon Vision** · Tel Aviv
2017 – 2021
- Detection and segmentation on aerial RGB imagery for defense clients; real-time on Ubuntu Linux

- Branch-and-bound combinatorial optimization for Israel Electric: 100x speedup via Gurobi

## EDUCATION
**B.Sc. Electrical Engineering** · Tel Aviv University · GPA 85 · 2013–2017

## TECHNICAL SKILLS
**Computer Vision:** Object detection, segmentation, tracking, anomaly detection
**Edge AI:** Ambarella CV22S, ONNX, INT8/FP16 quantization, TensorRT
**Frameworks:** PyTorch, TensorFlow, W&B, Docker, Git
"""
    out_pdf = tmp_path / "cv.pdf"
    result = generate_cv_pdf(cv_markdown, out_pdf)
    assert result == out_pdf
    assert out_pdf.exists()
    assert _count_pdf_pages(out_pdf) == 1
