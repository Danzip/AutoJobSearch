import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scorer import score_requirements, _determine_angle


def make_reqs(**kwargs):
    base = {
        "cv_relevance": 0, "dl_relevance": 0, "edge_ai_relevance": 0,
        "realtime_relevance": 0, "tracking_relevance": 0, "geometry_relevance": 0,
        "robotics_relevance": 0, "production_relevance": 0,
        "seniority": "senior", "domains": [], "concerns": [], "reasons_to_apply": [],
    }
    base.update(kwargs)
    return base


def test_high_cv_role_scores_above_60():
    reqs = make_reqs(
        cv_relevance=9, dl_relevance=8, tracking_relevance=8,
        production_relevance=7, realtime_relevance=7,
    )
    score, _, _ = score_requirements(reqs)
    assert score >= 60, f"Expected >= 60, got {score}"


def test_full_match_scores_above_80():
    reqs = make_reqs(
        cv_relevance=9, dl_relevance=9, edge_ai_relevance=9,
        realtime_relevance=9, tracking_relevance=9, production_relevance=9,
    )
    score, _, _ = score_requirements(reqs)
    assert score >= 80, f"Expected >= 80, got {score}"


def test_backend_penalty():
    reqs = make_reqs(cv_relevance=0, dl_relevance=0, domains=["backend", "fullstack"])
    score, explanation, _ = score_requirements(reqs)
    assert score < 20, f"Expected < 20 for pure backend role, got {score}"
    assert "PENALTY" in explanation


def test_junior_scores_less_than_senior():
    senior_reqs = make_reqs(cv_relevance=8, dl_relevance=8, seniority="senior")
    junior_reqs = make_reqs(cv_relevance=8, dl_relevance=8, seniority="junior")
    senior_score, _, _ = score_requirements(senior_reqs)
    junior_score, _, _ = score_requirements(junior_reqs)
    assert senior_score > junior_score


def test_score_bounded_0_100():
    reqs = make_reqs(
        cv_relevance=10, dl_relevance=10, edge_ai_relevance=10,
        realtime_relevance=10, tracking_relevance=10,
        production_relevance=10, geometry_relevance=10, robotics_relevance=10,
        seniority="senior",
    )
    score, _, _ = score_requirements(reqs)
    assert 0 <= score <= 100


def test_zero_score_floor():
    reqs = make_reqs(
        cv_relevance=0, dl_relevance=0, seniority="junior",
        domains=["backend", "fullstack"],
    )
    score, _, _ = score_requirements(reqs)
    assert score >= 0


def test_edge_ai_angle():
    reqs = make_reqs(edge_ai_relevance=9, realtime_relevance=9)
    angle = _determine_angle(reqs)
    assert "Edge AI" in angle or "real-time" in angle.lower()


def test_geometry_angle():
    reqs = make_reqs(geometry_relevance=10)
    angle = _determine_angle(reqs)
    assert "registration" in angle.lower() or "geometry" in angle.lower()


def test_production_angle():
    reqs = make_reqs(production_relevance=10)
    angle = _determine_angle(reqs)
    assert "Production" in angle or "pipeline" in angle.lower()


# ── Degree gap penalties ───────────────────────────────────────────────────────

def test_phd_required_penalizes_20pts():
    base = make_reqs(cv_relevance=8, dl_relevance=8)
    no_degree, _, _ = score_requirements(base)
    phd_req, _, _ = score_requirements({**base, "degree_required": "phd"})
    assert no_degree - phd_req == pytest.approx(20.0, abs=0.5)


def test_msc_required_penalizes_10pts():
    base = make_reqs(cv_relevance=8, dl_relevance=8)
    no_degree, _, _ = score_requirements(base)
    msc_req, _, _ = score_requirements({**base, "degree_required": "msc"})
    assert no_degree - msc_req == pytest.approx(10.0, abs=0.5)


def test_bsc_required_no_penalty():
    base = make_reqs(cv_relevance=8, dl_relevance=8)
    no_degree, _, _ = score_requirements(base)
    bsc_req, _, _ = score_requirements({**base, "degree_required": "bsc"})
    assert no_degree == bsc_req


def test_degree_penalty_in_explanation():
    reqs = make_reqs(cv_relevance=8, dl_relevance=8, degree_required="phd")
    _, explanation, _ = score_requirements(reqs)
    assert "PENALTY" in explanation
    assert "PhD" in explanation or "phd" in explanation.lower()


# ── Management role penalty ────────────────────────────────────────────────────

def test_management_role_penalty():
    normal = make_reqs(cv_relevance=8, dl_relevance=8, title="Senior CV Engineer")
    normal_score, _, _ = score_requirements(normal)

    mgmt = make_reqs(cv_relevance=8, dl_relevance=8, title="Team Lead CV Engineer")
    mgmt_score, _, _ = score_requirements(mgmt)

    assert normal_score - mgmt_score == pytest.approx(25.0, abs=0.5)


def test_management_penalty_in_explanation():
    reqs = make_reqs(cv_relevance=8, dl_relevance=8, title="Engineering Manager")
    _, explanation, _ = score_requirements(reqs)
    assert "PENALTY" in explanation
    assert "management" in explanation.lower() or "lead" in explanation.lower()
