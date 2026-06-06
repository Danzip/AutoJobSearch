import json
import re
import yaml
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROFILE_PATH = ROOT / "profile" / "candidate_profile.yaml"
PERSONAL_PATH = ROOT / "profile" / "personal.yaml"
NOTES_PATH = ROOT / "profile" / "notes.md"
CONFIG_PATH = ROOT / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_profile() -> dict:
    with open(PROFILE_PATH) as f:
        return yaml.safe_load(f)


def load_profile_notes() -> str:
    if not NOTES_PATH.exists():
        return ""
    return NOTES_PATH.read_text()


def save_profile_notes(text: str) -> None:
    NOTES_PATH.write_text(text)


def extract_json_from_text(text: str) -> dict:
    """Extract JSON from LLM output that may be wrapped in markdown code blocks."""
    # Try code block first
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    # Try raw JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON found in LLM response (first 300 chars): {text[:300]}")
