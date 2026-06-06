import time

from src.llm import LLMProvider
from src.prompts import ANALYZER_SYSTEM, analyzer_prompt
from src.utils import extract_json_from_text, load_config

def _dim_keys() -> list[str]:
    cfg = load_config()
    return [d["key"] for d in cfg.get("scoring", {}).get("dimensions", [])]


def _make_defaults() -> dict:
    base = {
        "company": "", "title": "", "seniority": "unknown",
        "degree_required": "none",
        "required_skills": [], "nice_to_have_skills": [], "domains": [],
        "reasons_to_apply": [], "concerns": [],
    }
    for key in _dim_keys():
        base[key] = 0
    return base


_DEFAULTS = _make_defaults()


def _clamp(data: dict) -> dict:
    defaults = _make_defaults()
    result = {**defaults, **data}
    for key in _dim_keys():
        result[key] = max(0, min(10, int(result.get(key, 0))))
    return result


def _truncate(description: str) -> str:
    cfg = load_config()
    max_chars = cfg.get("llm", {}).get("max_description_chars", 4000)
    if len(description) > max_chars:
        return description[:max_chars] + "\n[... truncated ...]"
    return description


def analyze_job(description: str, llm: LLMProvider) -> dict:
    """Single job analysis — used by the Streamlit UI."""
    prompt = analyzer_prompt(_truncate(description))
    raw = llm.complete(prompt, system=ANALYZER_SYSTEM, call_type="analyze")
    return _clamp(extract_json_from_text(raw))


def batch_analyze(descriptions: list[str]) -> list[dict]:
    """
    Submit all descriptions to the Anthropic Batch API in one shot.
    50% cheaper than sequential calls. Returns results in the same order.
    Falls back to sequential if batch API is unavailable.
    """
    import os
    import anthropic
    from src.token_tracker import log_usage

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    cfg = load_config()
    model = cfg.get("llm", {}).get("analyze_model", "claude-haiku-4-5-20251001")

    requests = [
        {
            "custom_id": f"job_{i}",
            "params": {
                "model": model,
                "max_tokens": 1024,
                "system": [
                    {
                        "type": "text",
                        "text": ANALYZER_SYSTEM,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [
                    {"role": "user", "content": analyzer_prompt(_truncate(desc))}
                ],
            },
        }
        for i, desc in enumerate(descriptions)
    ]

    print(f"  Submitting {len(requests)} jobs to Anthropic Batch API (50% discount)...")
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id} — waiting for completion...")

    # Poll until done
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        print(f"  Status: processing={counts.processing} "
              f"succeeded={counts.succeeded} errored={counts.errored}")
        if batch.processing_status == "ended":
            break
        time.sleep(8)

    # Collect results in order
    indexed: dict[int, dict] = {}
    total_in = total_out = 0
    for result in client.messages.batches.results(batch.id):
        idx = int(result.custom_id.split("_")[1])
        if result.result.type == "succeeded":
            msg = result.result.message
            total_in  += msg.usage.input_tokens
            total_out += msg.usage.output_tokens
            try:
                data = extract_json_from_text(msg.content[0].text)
                indexed[idx] = _clamp(data)
            except Exception:
                indexed[idx] = _DEFAULTS.copy()
        else:
            indexed[idx] = _DEFAULTS.copy()

    # Log aggregate usage (marked as batch — already at 50% effective rate)
    if total_in or total_out:
        log_usage(
            model=model + " (batch)",
            call_type="analyze",
            input_tokens=total_in,
            output_tokens=total_out,
        )
        print(f"  Batch done: {total_in:,} input + {total_out:,} output tokens")

    return [indexed.get(i, _DEFAULTS.copy()) for i in range(len(descriptions))]
