"""
Tests for prompt structure and content rules.
These tests assert properties of the prompt TEXT itself — they act as a guard
against accidental regressions in generation instructions. Each test is written
to FAIL on the old prompt text and PASS after the planned changes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.prompts import GENERATOR_SYSTEM, compress_and_package_prompt, comprehensive_cv_prompt


# ── Helpers ────────────────────────────────────────────────────────────────────

def _dummy_compress_prompt() -> str:
    job = {"title": "ML Engineer", "company": "Acme", "description": "Build ML models."}
    reqs = {"required_skills": ["PyTorch"], "domains": ["computer vision"], "seniority": "senior"}
    return compress_and_package_prompt(job, reqs, "draft content here", "General senior CV/DL engineer")


def _dummy_comprehensive_prompt() -> str:
    job = {"title": "ML Engineer", "company": "Acme", "description": "Build ML models.", "location": "Tel Aviv"}
    reqs = {"required_skills": ["PyTorch"], "domains": ["computer vision"], "seniority": "senior"}
    profile = {"stories": [], "skills": {}, "key_metrics": {}, "hard_limits": []}
    return comprehensive_cv_prompt(job, reqs, profile, "General senior CV/DL engineer")


# ── Bullet count: must allow 3-4 per role, not just 3 ─────────────────────────
# FAILS on old prompt: "select the strongest 3 bullets per role"

def test_compress_prompt_allows_4_bullets_per_role():
    """Compress prompt must say '3-4 bullets', not 'max 3'.
    FAILS on old prompt that hard-capped at 3 bullets — producing thin one-role CVs."""
    prompt = _dummy_compress_prompt()
    assert "3-4 bullets" in prompt, (
        "Compress prompt still says 'max 3 bullets' — this causes over-compression to one-liners. "
        "Must say '3-4 bullets per role'."
    )


def test_generator_system_allows_4_bullets_per_role():
    """GENERATOR_SYSTEM must allow 3-4 bullets per role.
    FAILS on old system prompt that said 'Max 3 bullets per role'."""
    assert "3-4 bullets" in GENERATOR_SYSTEM, (
        "GENERATOR_SYSTEM still hard-caps at 3 bullets — must say '3-4 bullets per role'."
    )


# ── Bullet depth: must explicitly require rich multi-line bullets ──────────────
# FAILS on old prompt: no instruction about bullet length/depth at all

def test_compress_prompt_requires_bullet_depth():
    """Compress prompt must explicitly instruct to preserve full bullet depth (multi-line sentences).
    FAILS on old prompt which had no such instruction, producing telegraphic one-liner fragments."""
    prompt = _dummy_compress_prompt()
    assert "BULLET DEPTH" in prompt, (
        "Compress prompt has no BULLET DEPTH instruction — bullets will be compressed to "
        "one-liner fragments that look like a wall of text in the PDF."
    )
    # Must mention wrapping to two lines or equivalent
    assert "2 lines" in prompt or "two lines" in prompt or "wrap" in prompt, (
        "BULLET DEPTH instruction does not mention multi-line wrapping — LLM will still over-compress."
    )


# ── Skills: blank line between categories must be in both prompts ──────────────

def test_compress_prompt_has_skills_separation_instruction():
    """Compress prompt must instruct blank line between skill categories so each appears on its own line.
    FAILS if the instruction is removed — categories collapse into one paragraph."""
    prompt = _dummy_compress_prompt()
    assert "blank line" in prompt.lower() and "category" in prompt.lower(), (
        "Compress prompt is missing blank-line-between-skill-categories instruction."
    )


def test_comprehensive_prompt_has_skills_separation_instruction():
    """Comprehensive prompt must also instruct blank line between skill categories."""
    prompt = _dummy_comprehensive_prompt()
    assert "blank line" in prompt.lower() and "category" in prompt.lower(), (
        "Comprehensive prompt is missing blank-line-between-skill-categories instruction."
    )


# ── No gap disclosure in the CV ────────────────────────────────────────────────

def test_generator_system_forbids_gap_disclosure():
    """GENERATOR_SYSTEM must explicitly forbid mentioning domain gaps or mismatches in the CV.
    FAILS on old system prompt that had no such rule — allowing 'adjacent skills' hedging."""
    assert "gap disclosure" in GENERATOR_SYSTEM or "domain mismatch" in GENERATOR_SYSTEM, (
        "GENERATOR_SYSTEM has no rule forbidding gap disclosure in the CV body — "
        "LLM will volunteer mismatches in summaries."
    )
