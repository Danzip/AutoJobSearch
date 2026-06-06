import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.referral_search import _parse_linkedin_hit, write_referral_targets_md, find_referral_targets


def test_parse_name_and_role():
    hit = {
        "title": "John Smith - Senior Engineer at Mobileye | LinkedIn",
        "href": "https://www.linkedin.com/in/johnsmith",
        "body": "",
    }
    result = _parse_linkedin_hit(hit)
    assert result is not None
    assert result["name"] == "John Smith"
    assert "Senior Engineer" in result["role"]
    assert result["linkedin_url"] == "https://www.linkedin.com/in/johnsmith"


def test_parse_non_linkedin_returns_none():
    hit = {
        "title": "Senior Engineer at Mobileye",
        "href": "https://mobileye.com/careers",
        "body": "",
    }
    assert _parse_linkedin_hit(hit) is None


def test_parse_linkedin_no_role():
    hit = {
        "title": "Jane Doe | LinkedIn",
        "href": "https://www.linkedin.com/in/janedoe",
        "body": "",
    }
    result = _parse_linkedin_hit(hit)
    assert result is not None
    assert result["name"] == "Jane Doe"
    assert result["role"] == ""


def test_parse_strips_company_from_role():
    hit = {
        "title": "Alice Lee - ML Engineer at Acme Corp | LinkedIn",
        "href": "https://www.linkedin.com/in/alicelee",
        "body": "",
    }
    result = _parse_linkedin_hit(hit)
    assert result["role"] == "ML Engineer"
    assert "Acme" not in result["role"]


def test_write_referral_targets_md_with_targets(tmp_path):
    job = {"company": "Mobileye", "title": "Senior CV Engineer"}
    targets = [
        {"name": "John Smith", "role": "Senior Engineer", "linkedin_url": "https://linkedin.com/in/johnsmith"},
        {"name": "Jane Doe", "role": "CV Researcher", "linkedin_url": "https://linkedin.com/in/janedoe"},
    ]
    out = write_referral_targets_md(tmp_path, job, targets)
    assert out.exists()
    text = out.read_text()
    assert "Mobileye" in text
    assert "John Smith" in text
    assert "Jane Doe" in text
    assert "Connection Message Template" in text
    assert "Do NOT send automatically" in text


def test_write_referral_targets_md_empty(tmp_path):
    job = {"company": "Acme", "title": "Engineer"}
    out = write_referral_targets_md(tmp_path, job, [])
    text = out.read_text()
    assert "No targets found" in text
    assert "Acme" in text


def test_write_referral_targets_md_filename(tmp_path):
    job = {"company": "Intel", "title": "DL Engineer"}
    out = write_referral_targets_md(tmp_path, job, [])
    assert out.name == "referral_targets.md"


def test_find_referral_targets_mocked(monkeypatch):
    fake_hits = [
        {"title": "Alice Lee - ML Engineer at Acme | LinkedIn",
         "href": "https://linkedin.com/in/alicelee", "body": ""},
        {"title": "Bob Katz - Software Engineer at Acme | LinkedIn",
         "href": "https://linkedin.com/in/bobkatz", "body": ""},
    ]

    class MockDDGS:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def text(self, query, max_results=10): return fake_hits

    import ddgs as _ddgs
    monkeypatch.setattr(_ddgs, "DDGS", MockDDGS)

    results = find_referral_targets("Acme", max_results=5)
    assert len(results) == 2
    assert results[0]["name"] == "Alice Lee"
    assert "ML Engineer" in results[0]["role"]


def test_find_referral_targets_handles_errors(monkeypatch):
    class BrokenDDGS:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def text(self, *a, **kw): raise RuntimeError("network error")

    import ddgs as _ddgs
    monkeypatch.setattr(_ddgs, "DDGS", BrokenDDGS)

    results = find_referral_targets("AnyCompany")
    assert results == []
