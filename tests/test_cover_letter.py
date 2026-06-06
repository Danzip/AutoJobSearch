"""Tests for cover letter generation."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generator import generate_application_content
from src.prompts import generator_prompt


# ── Fixtures ───────────────────────────────────────────────────────────────────

MINIMAL_PROFILE = {
    "personal": {
        "name": "Test User", "email": "test@example.com",
        "location": "Tel Aviv", "years_experience": 5,
        "education": {"degree": "B.Sc. CS", "institution": "TAU"},
    },
    "key_metrics": ["10 FPS baseline"],
    "hard_limits": ["Technology X"],
    "stories": [
        {
            "id": "story_a", "tags": ["detection", "production"],
            "headline": "Built detection pipeline",
            "body": "Trained YOLOv8 model achieving 0.45 mAP."
        }
    ],
    "skills": {"primary": ["Python", "PyTorch"]},
}

MINIMAL_JOB = {"company": "Acme Corp", "title": "CV Engineer", "location": "TLV", "description": ""}
MINIMAL_REQS = {
    "required_skills": ["Python"], "domains": ["computer_vision"],
    "seniority": "senior", "concerns": [], "reasons_to_apply": [],
}


def make_llm(json_response: str):
    llm = MagicMock()
    llm.complete.return_value = json_response
    return llm


# ── Generator returns cover_letter ─────────────────────────────────────────────

def test_cover_letter_in_output():
    """generate_application_content must return a cover_letter key."""
    raw = """{
        "cv_draft_markdown": "- bullet one",
        "linkedin_message": "Hi there",
        "recruiter_email": "Subject: Test\\n\\nBody.",
        "talking_points": ["point 1"],
        "cover_letter": "Para 1.\\n\\nPara 2.\\n\\nPara 3.\\n\\nPara 4."
    }"""
    content = generate_application_content(
        MINIMAL_JOB, MINIMAL_REQS, MINIMAL_PROFILE, "General", make_llm(raw)
    )
    assert "cover_letter" in content
    assert isinstance(content["cover_letter"], str)
    assert len(content["cover_letter"]) > 0


def test_cover_letter_fallback_when_missing():
    """If LLM omits cover_letter, output should still have the key (empty string ok)."""
    raw = """{
        "cv_draft_markdown": "- bullet",
        "linkedin_message": "Hi",
        "recruiter_email": "Subject: X\\n\\nBody.",
        "talking_points": []
    }"""
    content = generate_application_content(
        MINIMAL_JOB, MINIMAL_REQS, MINIMAL_PROFILE, "General", make_llm(raw)
    )
    assert "cover_letter" in content


def test_cover_letter_not_empty_string_when_provided():
    """cover_letter should be non-empty when LLM provides it."""
    import json as _json
    payload = {
        "cv_draft_markdown": "- b",
        "linkedin_message": "hi",
        "recruiter_email": "Subject: x\n\nbody",
        "talking_points": [],
        "cover_letter": "Opening paragraph.\n\nAchievement one.\n\nAchievement two.\n\nClose.",
    }
    content = generate_application_content(
        MINIMAL_JOB, MINIMAL_REQS, MINIMAL_PROFILE, "General", make_llm(_json.dumps(payload))
    )
    assert "Opening paragraph" in content["cover_letter"]
    assert len(content["cover_letter"]) > 20


# ── Prompt includes cover_letter instruction ───────────────────────────────────

def test_generator_prompt_requests_cover_letter():
    """The generator prompt JSON schema must request a cover_letter field."""
    prompt = generator_prompt(MINIMAL_JOB, MINIMAL_REQS, MINIMAL_PROFILE, "General")
    assert "cover_letter" in prompt


def test_generator_prompt_cover_letter_has_paragraph_guidance():
    """Cover letter guidance in prompt should mention paragraphs or structure."""
    prompt = generator_prompt(MINIMAL_JOB, MINIMAL_REQS, MINIMAL_PROFILE, "General")
    lower = prompt.lower()
    assert "paragraph" in lower or "para" in lower or "hook" in lower


# ── No em dashes rule propagated ──────────────────────────────────────────────

def test_cover_letter_rule_no_em_dash_in_prompt():
    """Generator system prompt should forbid em dashes (applies to cover letter too)."""
    from src.prompts import GENERATOR_SYSTEM
    assert "em dash" in GENERATOR_SYSTEM.lower() or "—" in GENERATOR_SYSTEM or "NO EM" in GENERATOR_SYSTEM


# ── Prompt is generic (not CV-engineering-specific) ──────────────────────────

def test_generator_system_is_generic():
    """GENERATOR_SYSTEM should not hardcode 'computer vision engineer'."""
    from src.prompts import GENERATOR_SYSTEM
    assert "computer vision engineer" not in GENERATOR_SYSTEM.lower()


def test_analyzer_system_is_generic():
    """ANALYZER_SYSTEM should not say 'specializing in computer vision'."""
    from src.prompts import ANALYZER_SYSTEM
    assert "specializing in computer vision" not in ANALYZER_SYSTEM.lower()
