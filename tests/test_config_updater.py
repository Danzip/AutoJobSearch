"""Tests for auto-generated scoring config from candidate profile."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import json

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_updater import suggest_scoring_config, apply_scoring_config, _degree_from_profile


# ── Fixtures ───────────────────────────────────────────────────────────────────

BIOENG_PROFILE = {
    "personal": {
        "name": "Dr. Sara",
        "education": {"degree": "Ph.D. Biomedical Engineering", "institution": "MIT"},
        "years_experience": 6,
    },
    "stories": [
        {"id": "s1", "tags": ["segmentation", "microscopy"], "headline": "Cell segmentation"},
        {"id": "s2", "tags": ["classification", "biomedical"], "headline": "Tissue classification"},
    ],
    "skills": {"primary": ["Python", "PyTorch", "microscopy imaging", "biomedical CV"]},
    "hard_limits": ["SLAM", "automotive"],
}

CV_PROFILE = {
    "personal": {
        "name": "Dan",
        "education": {"degree": "B.Sc. Electrical Engineering", "institution": "TAU"},
        "years_experience": 5,
    },
    "stories": [
        {"id": "s1", "tags": ["detection", "edge_ai"], "headline": "Object detection pipeline"},
    ],
    "skills": {"primary": ["PyTorch", "ONNX", "TensorRT"]},
    "hard_limits": ["SLAM", "NLP"],
}

SUGGESTED_CONFIG = {
    "dimensions": [
        {"key": "biomedical_cv", "label": "Biomedical CV", "max_pts": 25,
         "description": "10=core biomedical imaging role, 0=not relevant"},
        {"key": "segmentation_relevance", "label": "Segmentation / microscopy", "max_pts": 20,
         "description": "10=segmentation is core, 0=not relevant"},
        {"key": "dl_relevance", "label": "Deep Learning", "max_pts": 20,
         "description": "10=DL is primary, 0=not needed"},
        {"key": "production_relevance", "label": "Production deployment", "max_pts": 10,
         "description": "10=production required, 0=research only"},
        {"key": "research_relevance", "label": "Research / publications", "max_pts": 10,
         "description": "10=research role, 0=engineering only"},
    ],
    "excluded_domains": ["automotive", "robotics", "nlp"],
    "primary_keys": ["biomedical_cv", "segmentation_relevance"],
    "candidate_degree": "phd",
}


def make_llm(response: dict):
    llm = MagicMock()
    llm.complete.return_value = json.dumps(response)
    return llm


# ── _degree_from_profile ───────────────────────────────────────────────────────

def test_degree_from_profile_phd():
    assert _degree_from_profile(BIOENG_PROFILE) == "phd"


def test_degree_from_profile_bsc():
    assert _degree_from_profile(CV_PROFILE) == "bsc"


def test_degree_from_profile_msc():
    profile = {"personal": {"education": {"degree": "M.Sc. Computer Science"}}}
    assert _degree_from_profile(profile) == "msc"


def test_degree_from_profile_defaults_bsc():
    assert _degree_from_profile({}) == "bsc"


# ── suggest_scoring_config ─────────────────────────────────────────────────────

def test_suggest_returns_dimensions():
    llm = make_llm(SUGGESTED_CONFIG)
    result = suggest_scoring_config(BIOENG_PROFILE, llm)
    assert "dimensions" in result
    assert len(result["dimensions"]) > 0


def test_suggest_dimensions_have_required_keys():
    llm = make_llm(SUGGESTED_CONFIG)
    result = suggest_scoring_config(BIOENG_PROFILE, llm)
    for dim in result["dimensions"]:
        assert "key" in dim
        assert "label" in dim
        assert "max_pts" in dim
        assert "description" in dim


def test_suggest_returns_excluded_domains():
    llm = make_llm(SUGGESTED_CONFIG)
    result = suggest_scoring_config(BIOENG_PROFILE, llm)
    assert "excluded_domains" in result
    assert isinstance(result["excluded_domains"], list)


def test_suggest_returns_candidate_degree():
    llm = make_llm(SUGGESTED_CONFIG)
    result = suggest_scoring_config(BIOENG_PROFILE, llm)
    assert "candidate_degree" in result
    assert result["candidate_degree"] in ("bsc", "msc", "phd")


def test_suggest_uses_profile_degree_as_fallback():
    """If LLM omits candidate_degree, falls back to degree detected from profile."""
    incomplete = {k: v for k, v in SUGGESTED_CONFIG.items() if k != "candidate_degree"}
    llm = make_llm(incomplete)
    result = suggest_scoring_config(BIOENG_PROFILE, llm)
    assert result["candidate_degree"] == "phd"


# ── apply_scoring_config ───────────────────────────────────────────────────────

def test_apply_writes_dimensions_to_config(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("scoring:\n  threshold: 60\n")
    apply_scoring_config(SUGGESTED_CONFIG, config_path=cfg_path)
    import yaml
    written = yaml.safe_load(cfg_path.read_text())
    assert "dimensions" in written["scoring"]
    assert written["scoring"]["candidate_degree"] == "phd"


def test_apply_preserves_other_config_sections(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("llm:\n  model: haiku\nscoring:\n  threshold: 60\n")
    apply_scoring_config(SUGGESTED_CONFIG, config_path=cfg_path)
    import yaml
    written = yaml.safe_load(cfg_path.read_text())
    assert written["llm"]["model"] == "haiku"
    assert written["scoring"]["threshold"] == 60


# ── Degree penalty relative to candidate degree ───────────────────────────────

def test_phd_candidate_no_degree_penalty():
    """PhD candidate should never be penalized for degree requirements."""
    from src.scorer import score_requirements
    reqs = {
        "cv_relevance": 8, "dl_relevance": 8, "realtime_relevance": 0,
        "edge_ai_relevance": 0, "tracking_relevance": 5, "production_relevance": 5,
        "geometry_relevance": 0, "robotics_relevance": 0,
        "seniority": "senior", "domains": [], "title": "",
        "degree_required": "phd", "concerns": [], "reasons_to_apply": [],
    }
    phd_cfg = {"scoring": {**SUGGESTED_CONFIG, "threshold": 60}}
    with patch("src.scorer.load_config", return_value=phd_cfg):
        score_phd, explanation, _ = score_requirements(reqs)
    assert "PENALTY" not in explanation or "degree" not in explanation.lower()


def test_msc_candidate_penalized_for_phd_only():
    """MSc candidate: PhD required should penalize, MSc required should not."""
    from src.scorer import score_requirements
    base_reqs = {
        "cv_relevance": 8, "dl_relevance": 8, "realtime_relevance": 0,
        "edge_ai_relevance": 0, "tracking_relevance": 5, "production_relevance": 5,
        "geometry_relevance": 0, "robotics_relevance": 0,
        "seniority": "senior", "domains": [], "title": "",
        "concerns": [], "reasons_to_apply": [],
    }
    msc_cfg = {"scoring": {
        "dimensions": SUGGESTED_CONFIG["dimensions"],
        "excluded_domains": [],
        "primary_keys": ["biomedical_cv"],
        "candidate_degree": "msc",
        "threshold": 60,
    }}
    with patch("src.scorer.load_config", return_value=msc_cfg):
        score_msc_req, expl_msc, _ = score_requirements({**base_reqs, "degree_required": "msc"})
        score_phd_req, expl_phd, _ = score_requirements({**base_reqs, "degree_required": "phd"})

    assert score_msc_req > score_phd_req, "MSc candidate: PhD role should score lower than MSc role"
