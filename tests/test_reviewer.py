import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reviewer import review_cv
from src.prompts import reviewer_prompt, REVIEWER_SYSTEM


class MockLLM:
    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def complete(self, prompt, system="", **kwargs):
        self.last_prompt = prompt
        return self.response


def test_reviewer_returns_string():
    llm = MockLLM('{"improved_cv": "- Improved bullet", "flags": []}')
    result = review_cv("job description", "- Original bullet", llm)
    assert isinstance(result, str)
    assert len(result) > 0


def test_reviewer_returns_improved_cv():
    improved = "- Optimized bullet with JD keywords"
    llm = MockLLM(f'{{"improved_cv": "{improved}", "flags": ["missing: TensorRT"]}}')
    result = review_cv("TensorRT edge deployment", "- Vague bullet", llm)
    assert result == improved


def test_reviewer_uses_jd_in_prompt():
    llm = MockLLM('{"improved_cv": "- bullet", "flags": []}')
    review_cv("UNIQUE_JD_MARKER_XYZ", "- bullet", llm)
    assert "UNIQUE_JD_MARKER_XYZ" in llm.last_prompt


def test_reviewer_uses_cv_in_prompt():
    llm = MockLLM('{"improved_cv": "- bullet", "flags": []}')
    review_cv("job description", "- UNIQUE_CV_MARKER_ABC", llm)
    assert "UNIQUE_CV_MARKER_ABC" in llm.last_prompt


def test_reviewer_falls_back_on_parse_error():
    llm = MockLLM("not valid json at all")
    original = "- Original bullet unchanged"
    result = review_cv("job", original, llm)
    assert result == original


def test_reviewer_system_mentions_review():
    assert "review" in REVIEWER_SYSTEM.lower()


def test_reviewer_prompt_contains_both_inputs():
    prompt = reviewer_prompt("JD CONTENT HERE", "CV CONTENT HERE")
    assert "JD CONTENT HERE" in prompt
    assert "CV CONTENT HERE" in prompt
