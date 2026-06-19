import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cv_validator import missing_employers, missing_required_skills


# ── missing_employers ───────────────────────────────────────────────────────

def test_missing_employers_returns_empty_when_all_present():
    cv = """
    Gentex / Guardian Optical Technologies | 2021-2023
    Razor Labs / Axon Vision | 2017-2021
    Independent Research | 2024-2026
    """
    assert missing_employers(cv) == []


def test_missing_employers_flags_dropped_employer():
    """Regression: a 2024-06 batch silently dropped Razor Labs from 8+ CVs,
    leaving an unexplained 4-year employment gap."""
    cv = """
    Gentex / Guardian Optical Technologies | 2021-2023
    Independent Research | 2024-2026
    """
    assert missing_employers(cv) == ["Razor Labs"]


def test_missing_employers_accepts_legal_entity_aliases():
    """Axon Vision is the same company as Razor Labs under a different legal entity."""
    cv = "Worked at Axon Vision and Guardian Optical Technologies and did Independent Research."
    assert missing_employers(cv) == []


def test_missing_employers_flags_all_when_cv_is_empty():
    assert set(missing_employers("")) == {"Gentex", "Razor Labs", "Independent Research"}


# ── missing_required_skills ─────────────────────────────────────────────────

def test_missing_required_skills_returns_empty_when_all_covered():
    cv = "Experience with PyTorch, ONNX, and real-time inference optimization."
    reqs = {"required_skills": ["PyTorch", "ONNX"]}
    assert missing_required_skills(cv, reqs) == []


def test_missing_required_skills_flags_uncovered_skill():
    cv = "Experience with PyTorch and computer vision."
    reqs = {"required_skills": ["PyTorch", "Kubernetes"]}
    assert missing_required_skills(cv, reqs) == ["Kubernetes"]


def test_missing_required_skills_handles_no_requirements():
    assert missing_required_skills("anything", {}) == []
