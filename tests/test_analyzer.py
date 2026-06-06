import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import extract_json_from_text
from src.analyzer import analyze_job


# ── extract_json_from_text ────────────────────────────────────────────────────

def test_extract_from_json_code_block():
    text = '```json\n{"company": "Acme", "cv_relevance": 8}\n```'
    result = extract_json_from_text(text)
    assert result["company"] == "Acme"
    assert result["cv_relevance"] == 8


def test_extract_from_plain_code_block():
    text = '```\n{"title": "CV Engineer"}\n```'
    result = extract_json_from_text(text)
    assert result["title"] == "CV Engineer"


def test_extract_raw_json():
    text = 'Here is the result: {"cv_relevance": 7, "dl_relevance": 5}'
    result = extract_json_from_text(text)
    assert result["cv_relevance"] == 7


def test_raises_on_no_json():
    with pytest.raises(ValueError, match="No JSON found"):
        extract_json_from_text("No JSON anywhere in this response.")


# ── analyze_job (mock LLM) ────────────────────────────────────────────────────

class MockLLM:
    def __init__(self, response: str):
        self.response = response

    def complete(self, prompt: str, system: str = "", **kwargs) -> str:
        return self.response


SAMPLE_RESPONSE = json.dumps({
    "company": "TestCo",
    "title": "Senior CV Engineer",
    "seniority": "senior",
    "required_skills": ["PyTorch", "OpenCV"],
    "nice_to_have_skills": ["ONNX"],
    "domains": ["computer_vision", "deep_learning"],
    "cv_relevance": 9,
    "dl_relevance": 8,
    "edge_ai_relevance": 5,
    "realtime_relevance": 6,
    "tracking_relevance": 7,
    "geometry_relevance": 3,
    "robotics_relevance": 0,
    "production_relevance": 7,
    "reasons_to_apply": ["Core CV role", "Edge deployment"],
    "concerns": [],
})


def test_analyze_job_returns_dict():
    llm = MockLLM(SAMPLE_RESPONSE)
    result = analyze_job("Some job description", llm)
    assert isinstance(result, dict)
    assert result["company"] == "TestCo"
    assert result["cv_relevance"] == 9


def test_analyze_job_clamps_scores():
    bad_response = json.dumps({**json.loads(SAMPLE_RESPONSE), "cv_relevance": 15})
    llm = MockLLM(bad_response)
    result = analyze_job("job", llm)
    assert result["cv_relevance"] == 10


def test_analyze_job_fills_defaults():
    minimal = json.dumps({"title": "Engineer"})
    llm = MockLLM(minimal)
    result = analyze_job("job", llm)
    assert result["cv_relevance"] == 0
    assert result["required_skills"] == []
    assert result["seniority"] == "unknown"
