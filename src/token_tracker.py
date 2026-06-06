"""
Logs token usage for every LLM call and provides summary stats.
Log file: data/token_usage.jsonl  (one JSON line per call)
"""

import json
from datetime import datetime
from pathlib import Path

_LOG_PATH = Path(__file__).parent.parent / "data" / "token_usage.jsonl"

# Anthropic pricing per million tokens (USD) as of 2025
_PRICING = {
    "claude-sonnet-4-6": {
        "input": 3.00, "output": 15.00,
        "cache_read": 0.30, "cache_write": 3.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80, "output": 4.00,
        "cache_read": 0.08, "cache_write": 1.00,
    },
    "gpt-4o": {
        "input": 2.50, "output": 10.00,
        "cache_read": 1.25, "cache_write": 0.0,
    },
}
_DEFAULT_PRICING = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}


def log_usage(
    model: str,
    call_type: str,        # "analyze" | "generate" | "other"
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> dict:
    pricing = _PRICING.get(model, _DEFAULT_PRICING)
    cost = (
        (input_tokens - cache_read_tokens) / 1_000_000 * pricing["input"]
        + output_tokens               / 1_000_000 * pricing["output"]
        + cache_read_tokens           / 1_000_000 * pricing["cache_read"]
        + cache_write_tokens          / 1_000_000 * pricing["cache_write"]
    )
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "type": call_type,
        "in": input_tokens,
        "out": output_tokens,
        "cache_read": cache_read_tokens,
        "cache_write": cache_write_tokens,
        "cost_usd": round(cost, 6),
    }
    _LOG_PATH.parent.mkdir(exist_ok=True)
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_log() -> list[dict]:
    if not _LOG_PATH.exists():
        return []
    records = []
    with open(_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def summary() -> dict:
    records = read_log()
    if not records:
        return {}

    total_in    = sum(r["in"]          for r in records)
    total_out   = sum(r["out"]         for r in records)
    total_cache = sum(r.get("cache_read", 0) for r in records)
    total_cost  = sum(r["cost_usd"]    for r in records)
    total_calls = len(records)

    by_type: dict[str, dict] = {}
    for r in records:
        t = r["type"]
        by_type.setdefault(t, {"calls": 0, "tokens": 0, "cost": 0.0})
        by_type[t]["calls"]  += 1
        by_type[t]["tokens"] += r["in"] + r["out"]
        by_type[t]["cost"]   += r["cost_usd"]

    return {
        "total_calls":        total_calls,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cache_hits":   total_cache,
        "total_cost_usd":     round(total_cost, 4),
        "by_type":            by_type,
    }


def print_summary():
    s = summary()
    if not s:
        print("No token usage recorded yet.")
        return
    print(f"\n{'─'*50}")
    print(f"  Token Usage Summary")
    print(f"{'─'*50}")
    print(f"  Total calls   : {s['total_calls']}")
    print(f"  Input tokens  : {s['total_input_tokens']:,}")
    print(f"  Output tokens : {s['total_output_tokens']:,}")
    print(f"  Cache hits    : {s['total_cache_hits']:,}")
    print(f"  Total cost    : ${s['total_cost_usd']:.4f}")
    print(f"{'─'*50}")
    for t, info in s["by_type"].items():
        print(f"  {t:<12}  {info['calls']:>3} calls  {info['tokens']:>7,} tokens  ${info['cost']:.4f}")
    print(f"{'─'*50}\n")
