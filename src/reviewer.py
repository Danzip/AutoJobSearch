from src.llm import LLMProvider
from src.prompts import REVIEWER_SYSTEM, reviewer_prompt
from src.utils import extract_json_from_text


def review_cv(jd: str, cv_draft: str, llm: LLMProvider) -> str:
    """
    Run a reviewer pass on the CV draft.
    Returns the improved CV markdown, or original draft if parsing fails.
    """
    prompt = reviewer_prompt(jd, cv_draft)
    raw = llm.complete(prompt, system=REVIEWER_SYSTEM, call_type="review")
    try:
        data = extract_json_from_text(raw)
        improved = data.get("improved_cv", "").strip()
        return improved if improved else cv_draft
    except Exception:
        return cv_draft
