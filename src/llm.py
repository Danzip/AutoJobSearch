import os
from abc import ABC, abstractmethod
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "", call_type: str = "other") -> str: ...


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-6"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def complete(self, prompt: str, system: str = "", call_type: str = "other") -> str:
        from src.token_tracker import log_usage
        from src.utils import load_config

        cfg = load_config()
        warn_limit = cfg.get("token_tracking", {}).get("warn_per_call_tokens", 8000)

        msg = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": system or "You are a helpful assistant.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        usage = msg.usage
        record = log_usage(
            model=self.model,
            call_type=call_type,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
        )

        total = usage.input_tokens + usage.output_tokens
        if total > warn_limit:
            print(f"  [tokens] {call_type} call: {total:,} tokens (${record['cost_usd']:.4f})")
        else:
            print(f"  [tokens] {call_type}: in={usage.input_tokens} out={usage.output_tokens} "
                  f"cache_hit={record['cache_read']} cost=${record['cost_usd']:.4f}")

        return msg.content[0].text


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o"):
        import openai
        self.client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = model

    def complete(self, prompt: str, system: str = "", call_type: str = "other") -> str:
        from src.token_tracker import log_usage

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        usage = resp.usage
        log_usage(
            model=self.model,
            call_type=call_type,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            cache_read_tokens=getattr(usage, "prompt_tokens_details", {}) and
                              getattr(usage.prompt_tokens_details, "cached_tokens", 0),
        )
        return resp.choices[0].message.content


def get_llm(provider: str = None, model: str = None) -> LLMProvider:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    provider = provider or cfg.get("llm", {}).get("provider", "anthropic")
    model = model or None

    if provider == "anthropic":
        return AnthropicProvider(model=model or "claude-sonnet-4-6")
    elif provider == "openai":
        return OpenAIProvider(model=model or "gpt-4o")
    else:
        raise ValueError(f"Unknown LLM provider: {provider!r}")


def get_analyze_llm() -> LLMProvider:
    """Cheaper model for JSON extraction — Haiku by default."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    provider = cfg.get("llm", {}).get("provider", "anthropic")
    model = cfg.get("llm", {}).get("analyze_model", "claude-haiku-4-5-20251001")
    if provider == "anthropic":
        return AnthropicProvider(model=model)
    return get_llm(provider)


def get_generate_llm() -> LLMProvider:
    """Better model for CV/message generation — Sonnet by default."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    provider = cfg.get("llm", {}).get("provider", "anthropic")
    model = cfg.get("llm", {}).get("generate_model", "claude-sonnet-4-6")
    if provider == "anthropic":
        return AnthropicProvider(model=model)
    return get_llm(provider)


def get_review_llm() -> LLMProvider:
    """Cheap model for the reviewer pass — Haiku by default."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    provider = cfg.get("llm", {}).get("provider", "anthropic")
    model = cfg.get("llm", {}).get("review_model", "claude-haiku-4-5-20251001")
    if provider == "anthropic":
        return AnthropicProvider(model=model)
    return get_llm(provider)
