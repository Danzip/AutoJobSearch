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


# ── CSS bullet spacing ─────────────────────────────────────────────────────────

def test_css_li_margin_bottom_at_least_4px():
    """Base li margin-bottom must be > 2px so bullets aren't smushed together."""
    import re
    m = re.search(r"li\s*\{[^}]*margin-bottom:\s*(\d+)px", _CV_CSS)
    assert m, "li { margin-bottom: Xpx } not found in _CV_CSS"
    assert int(m.group(1)) >= 4, f"li margin-bottom is {m.group(1)}px — too tight, need >= 4px"


def test_css_loose_list_li_p_margin_reset():
    """li > p must have margin: 0 so loose-list items don't double-space."""
    assert "li > p" in _CV_CSS, "li > p rule missing from _CV_CSS"
    import re
    m = re.search(r"li\s*>\s*p\s*\{([^}]*)\}", _CV_CSS)
    assert m, "li > p { ... } block not found in _CV_CSS"
    assert "margin: 0" in m.group(1), "li > p must set margin: 0 to prevent double-spacing"


# ── Markdown: tight vs loose list HTML structure ───────────────────────────────

def _render_md(text: str) -> str:
    import markdown
    return markdown.markdown(text)


def test_tight_list_renders_without_p_wrapper():
    """Consecutive bullets (no blank line) produce <li>text</li>, not <li><p>text</p></li>."""
    html = _render_md("- bullet one\n- bullet two\n- bullet three\n")
    assert "<li><p>" not in html
    assert "<li>bullet one</li>" in html


def test_loose_list_renders_with_p_wrapper():
    """Bullets separated by blank lines (different project groups) produce <li>...<p>...</p>...</li>."""
    html = _render_md("- bullet one\n\n- bullet two\n\n- bullet three\n")
    # python-markdown renders loose list items with <p> inside <li> (possibly with whitespace)
    assert "<p>bullet one</p>" in html
    assert "<p>bullet two</p>" in html
    # Verify the <p> is nested inside <li>, not at top level
    assert html.index("<p>bullet one</p>") > html.index("<li>")


def test_mixed_tight_loose_list_groups():
    """Blank line between project groups causes items after the gap to be wrapped in <p>."""
    md = "- d-fine bullet 1\n- d-fine bullet 2\n\n- muze bullet\n"
    html = _render_md(md)
    # Items after the blank line get <p> wrapping (loose item behaviour)
    assert "<p>muze bullet</p>" in html
    assert "d-fine bullet 1" in html


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
