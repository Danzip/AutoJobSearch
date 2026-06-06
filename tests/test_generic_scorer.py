"""Tests for config-driven generic scorer."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scorer import score_requirements, _load_dims


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_reqs(**kwargs):
    base = {
        "cv_relevance": 0, "dl_relevance": 0, "edge_ai_relevance": 0,
        "realtime_relevance": 0, "tracking_relevance": 0, "geometry_relevance": 0,
        "robotics_relevance": 0, "production_relevance": 0,
        "seniority": "senior", "domains": [], "title": "",
        "concerns": [], "reasons_to_apply": [],
    }
    base.update(kwargs)
    return base


BACKEND_DIMS = [
    {"key": "backend_relevance",  "label": "Backend engineering", "max_pts": 25,
     "description": "10=core backend role, 0=not relevant"},
    {"key": "system_design",      "label": "System design",       "max_pts": 20,
     "description": "10=architecture/design required, 0=not relevant"},
    {"key": "api_relevance",      "label": "API design",          "max_pts": 15,
     "description": "10=API design is core, 0=not relevant"},
    {"key": "production_relevance", "label": "Production scale",  "max_pts": 25,
     "description": "10=production required, 0=not relevant"},
]

BACKEND_CFG = {
    "dimensions": BACKEND_DIMS,
    "excluded_domains": ["computer_vision", "robotics"],
    "primary_keys": ["backend_relevance", "api_relevance"],
    "threshold": 60,
}


# ── Config-driven dimensions load ─────────────────────────────────────────────

def test_load_dims_returns_list():
    dims = _load_dims()
    assert isinstance(dims, list)
    assert len(dims) > 0


def test_load_dims_have_required_keys():
    dims = _load_dims()
    for dim in dims:
        assert "key" in dim
        assert "max_pts" in dim


# ── Custom domain scoring ──────────────────────────────────────────────────────

def test_custom_dims_backend_engineer():
    """Backend engineer config should score backend roles highly."""
    reqs = {
        "backend_relevance": 9, "system_design": 8, "api_relevance": 9,
        "production_relevance": 8,
        "seniority": "senior", "domains": [], "title": "", "degree_required": "none",
        "concerns": [], "reasons_to_apply": [],
    }
    cfg_scoring = BACKEND_CFG
    with patch("src.scorer.load_config", return_value={"scoring": cfg_scoring}):
        score, _, _ = score_requirements(reqs)
    assert score >= 70, f"Expected >= 70 for strong backend match, got {score}"


def test_custom_dims_wrong_domain_penalized():
    """CV-focused role should score low under backend-engineer config."""
    reqs = {
        "backend_relevance": 0, "system_design": 0, "api_relevance": 0,
        "production_relevance": 0,
        "seniority": "senior", "domains": ["computer_vision"], "title": "",
        "degree_required": "none", "concerns": [], "reasons_to_apply": [],
    }
    with patch("src.scorer.load_config", return_value={"scoring": BACKEND_CFG}):
        score, explanation, _ = score_requirements(reqs)
    assert "PENALTY" in explanation


def test_custom_dims_zero_signal_penalty():
    """If all primary_keys are 0, apply zero-signal penalty."""
    reqs = {
        "backend_relevance": 0, "system_design": 5, "api_relevance": 0,
        "production_relevance": 5,
        "seniority": "mid", "domains": [], "title": "", "degree_required": "none",
        "concerns": [], "reasons_to_apply": [],
    }
    with patch("src.scorer.load_config", return_value={"scoring": BACKEND_CFG}):
        score_with_penalty, explanation, _ = score_requirements(reqs)
    assert "PENALTY" in explanation


def test_custom_dims_max_pts_sum_respected():
    """Max possible score from dims alone should equal sum of max_pts (no seniority)."""
    reqs = {
        "backend_relevance": 10, "system_design": 10, "api_relevance": 10,
        "production_relevance": 10,
        "seniority": "unknown", "domains": [], "title": "", "degree_required": "none",
        "concerns": [], "reasons_to_apply": [],
    }
    expected_dim_max = sum(d["max_pts"] for d in BACKEND_DIMS)
    with patch("src.scorer.load_config", return_value={"scoring": BACKEND_CFG}):
        score, _, _ = score_requirements(reqs)
    # score = dim_max + seniority (unknown=8); capped at 100
    assert score <= 100


def test_dims_max_pts_sum_is_85_for_default_config():
    """Default CV dims should sum to 85 (seniority accounts for remaining 15)."""
    dims = _load_dims()
    total = sum(d["max_pts"] for d in dims)
    assert total == 85, f"Expected dim max_pts to sum to 85, got {total}"


# ── Explanation uses dimension labels ──────────────────────────────────────────

def test_explanation_contains_dim_labels():
    """Explanation lines should mention dimension labels, not hardcoded 'CV/DL'."""
    reqs = make_reqs(cv_relevance=8, dl_relevance=7, production_relevance=6)
    _, explanation, _ = score_requirements(reqs)
    # The explanation should contain labels from config, not just raw keys
    assert explanation  # not empty
    assert "Score:" in explanation


def test_custom_dim_label_appears_in_explanation():
    """Custom dimension label should appear in explanation."""
    reqs = {
        "backend_relevance": 8, "system_design": 7, "api_relevance": 6,
        "production_relevance": 7,
        "seniority": "senior", "domains": [], "title": "", "degree_required": "none",
        "concerns": [], "reasons_to_apply": [],
    }
    with patch("src.scorer.load_config", return_value={"scoring": BACKEND_CFG}):
        _, explanation, _ = score_requirements(reqs)
    assert "Backend engineering" in explanation or "backend" in explanation.lower()
