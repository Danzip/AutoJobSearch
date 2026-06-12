import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.job_search_linkedin import search_linkedin_jobs


def _make_jobs_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal DataFrame matching JobSpy's output schema."""
    defaults = {
        "job_url": None,
        "title": None,
        "company": None,
        "date_posted": None,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def test_returns_list_of_dicts(monkeypatch):
    df = _make_jobs_df([
        {
            "job_url": "https://www.linkedin.com/jobs/view/111",
            "title": "Computer Vision Engineer",
            "company": "Mobileye",
            "date_posted": date(2026, 6, 10),
        }
    ])
    with patch("jobspy.scrape_jobs", return_value=df):
        results = search_linkedin_jobs("computer vision")

    assert isinstance(results, list)
    assert len(results) == 1
    r = results[0]
    assert r["url"] == "https://www.linkedin.com/jobs/view/111"
    assert r["title"] == "Computer Vision Engineer"
    assert r["company"] == "Mobileye"
    assert r["board"] == "LinkedIn"
    assert r["posted_date"] == "2026-06-10"


def test_skips_rows_without_linkedin_url(monkeypatch):
    df = _make_jobs_df([
        {"job_url": "https://www.linkedin.com/jobs/view/222", "title": "A", "company": "X", "date_posted": None},
        {"job_url": "", "title": "B", "company": "Y", "date_posted": None},
        {"job_url": None, "title": "C", "company": "Z", "date_posted": None},
        {"job_url": "https://notlinkedin.com/job/333", "title": "D", "company": "W", "date_posted": None},
    ])
    with patch("jobspy.scrape_jobs", return_value=df):
        results = search_linkedin_jobs("anything")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.linkedin.com/jobs/view/222"


def test_handles_none_date(monkeypatch):
    df = _make_jobs_df([
        {"job_url": "https://www.linkedin.com/jobs/view/123", "title": "T", "company": "C", "date_posted": None},
    ])
    with patch("jobspy.scrape_jobs", return_value=df):
        results = search_linkedin_jobs("x")

    assert results[0]["posted_date"] == ""


def test_returns_empty_on_jobspy_exception(monkeypatch, capsys):
    with patch("jobspy.scrape_jobs", side_effect=RuntimeError("network error")):
        results = search_linkedin_jobs("anything")

    assert results == []
    captured = capsys.readouterr()
    assert "JobSpy error" in captured.out


def test_returns_empty_on_import_error(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "jobspy":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    # Re-import the module so the import path is exercised fresh
    import importlib
    import src.job_search_linkedin as mod
    importlib.reload(mod)

    results = mod.search_linkedin_jobs("anything")
    assert results == []


def test_multiple_results(monkeypatch):
    df = _make_jobs_df([
        {"job_url": f"https://www.linkedin.com/jobs/view/{i}", "title": f"Job {i}",
         "company": f"Co{i}", "date_posted": date(2026, 6, i + 1)}
        for i in range(1, 6)
    ])
    with patch("jobspy.scrape_jobs", return_value=df):
        results = search_linkedin_jobs("cv")

    assert len(results) == 5
    assert all(r["board"] == "LinkedIn" for r in results)
    assert results[0]["posted_date"] == "2026-06-02"
