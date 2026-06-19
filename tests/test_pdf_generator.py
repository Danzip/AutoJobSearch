import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pdf_generator import (
    _count_pdf_pages,
    _extract_cv_section,
    _CSS_SHRINK_OVERRIDES,
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
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("weasyprint not installed")

    cv_markdown = """# Daniel Ziv - Computer Vision Engineer
dziv94@gmail.com | Tel Aviv

## SUMMARY
Computer vision engineer with experience in real-time detection and tracking.

## EXPERIENCE

**Acme Corp** | *Engineer*   2021-2023 | Israel
- Built a thing
- Built another thing

## EDUCATION
B.Sc. Electrical Engineering | Tel Aviv University   2013-2017

## TECHNICAL SKILLS
**Computer Vision:** Object detection, tracking
"""
    out_pdf = tmp_path / "cv.pdf"
    result = generate_cv_pdf(cv_markdown, out_pdf)
    assert result == out_pdf
    assert out_pdf.exists()
    assert _count_pdf_pages(out_pdf) == 1
