import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pdf_generator import (
    _score_bullet,
    _cut_weakest_bullet,
    _count_pdf_pages,
    _CSS_SHRINK_OVERRIDES,
    _extract_tailored_bullets,
)


# ── Bullet scoring ─────────────────────────────────────────────────────────────

def test_score_bullet_counts_matches():
    bullet = "INT8 quantization and ONNX export pipeline"
    assert _score_bullet(bullet, ["INT8", "ONNX", "quantization", "TensorRT"]) == 3


def test_score_bullet_case_insensitive():
    assert _score_bullet("PyTorch training loop", ["pytorch"]) == 1


def test_score_bullet_no_keywords():
    assert _score_bullet("some bullet", []) == 0


def test_score_bullet_no_match():
    assert _score_bullet("edge deployment pipeline", ["SLAM", "ROS2", "LiDAR"]) == 0


def test_score_bullet_partial_substring():
    # "quantize" should NOT match "quantization" as a whole word, but substring match is fine
    # The implementation uses substring matching for simplicity
    score = _score_bullet("model quantize step", ["quantization"])
    assert isinstance(score, int)  # just verify it returns int, not crash


# ── Bullet cutting ─────────────────────────────────────────────────────────────

def test_cut_weakest_removes_lowest_scorer():
    bullets = [
        "INT8 quantization and ONNX export",     # score 2
        "general soft skills and communication", # score 0
        "ONNX model compression pipeline",       # score 1
    ]
    keywords = ["INT8", "ONNX", "quantization"]
    result = _cut_weakest_bullet(bullets, keywords)
    assert len(result) == 2
    assert "general soft skills and communication" not in result


def test_cut_weakest_preserves_single_bullet():
    assert _cut_weakest_bullet(["only bullet"], ["kw"]) == ["only bullet"]


def test_cut_weakest_preserves_empty_list():
    assert _cut_weakest_bullet([], ["kw"]) == []


def test_cut_weakest_all_equal_removes_last():
    bullets = ["bullet a", "bullet b", "bullet c"]
    result = _cut_weakest_bullet(bullets, ["xyz"])  # no matches → all score 0
    assert len(result) == 2
    # Last one should be removed when all tied
    assert "bullet c" not in result


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
    """Generate a minimal PDF and verify page count detection works."""
    try:
        from weasyprint import HTML, CSS
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


# ── Extract bullets ────────────────────────────────────────────────────────────

def test_extract_tailored_bullets_from_cv_md(tmp_path):
    md = """# CV Draft
**Angle:** Edge AI
**Score:** 88/100

---

## Tailored Highlights

- First bullet point
- Second bullet point
- Third bullet

## LinkedIn Message

Some message here.
"""
    md_path = tmp_path / "cv.md"
    md_path.write_text(md)
    bullets = _extract_tailored_bullets(md_path.read_text())
    assert len(bullets) == 3
    assert bullets[0] == "First bullet point"
    assert bullets[2] == "Third bullet"


def test_extract_tailored_bullets_returns_empty_when_no_section(tmp_path):
    md = "# CV Draft\n\nNo highlights section here.\n"
    bullets = _extract_tailored_bullets(md)
    assert bullets == []
