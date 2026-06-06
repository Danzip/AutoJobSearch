"""
Tests for parallel Comeet scraping — scrape_batch and parallel company discovery.
No real network calls; Playwright is mocked at the _playwright_scrape boundary.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.base import ScrapedJob
from src.scrapers.comeet import scrape_batch
from src.job_search_comeet import search_comeet_companies


def _job(description: str, title: str = "Engineer") -> ScrapedJob:
    return ScrapedJob(title=title, company="TestCo", description=description, source="comeet")


FAKE_COMPANIES = [
    {"slug": "acme", "name": "Acme"},
    {"slug": "globex", "name": "Globex"},
]

ACME_JOBS = [
    {"title": "Computer Vision Engineer", "location": "Tel Aviv",
     "url": "https://www.comeet.com/jobs/acme/1/cv-engineer/A1"},
    {"title": "Sales Manager", "location": "Tel Aviv",
     "url": "https://www.comeet.com/jobs/acme/1/sales-manager/A2"},
]

GLOBEX_JOBS = [
    {"title": "Deep Learning Researcher", "location": "Haifa",
     "url": "https://www.comeet.com/jobs/globex/1/dl-researcher/G1"},
]


# ── scrape_batch ──────────────────────────────────────────────────────────────

class TestScrapeBatch:
    def test_returns_results_in_input_order(self):
        """Output order matches input URL order even when threads finish out-of-order."""
        urls = [
            "https://www.comeet.com/jobs/a/1/eng/A1",
            "https://www.comeet.com/jobs/b/1/eng/B1",
            "https://www.comeet.com/jobs/c/1/eng/C1",
        ]
        jobs_by_url = {url: _job(f"desc-{i}") for i, url in enumerate(urls)}

        with patch("src.scrapers.comeet._playwright_scrape", side_effect=lambda u: jobs_by_url[u]):
            results = scrape_batch(urls, workers=3)

        assert len(results) == 3
        assert [r.description for r in results] == ["desc-0", "desc-1", "desc-2"]

    def test_failed_url_returns_empty_job_others_unaffected(self):
        """If one URL raises, that slot gets an empty ScrapedJob; others succeed."""
        urls = [
            "https://www.comeet.com/jobs/good/1/eng/G1",
            "https://www.comeet.com/jobs/bad/1/eng/B1",
            "https://www.comeet.com/jobs/good/2/eng/G2",
        ]

        def _mock(url):
            if "bad" in url:
                raise RuntimeError("Playwright timeout")
            return _job("real description")

        with patch("src.scrapers.comeet._playwright_scrape", side_effect=_mock):
            results = scrape_batch(urls, workers=3)

        assert results[0].description == "real description"
        assert results[1].description == ""   # empty default
        assert results[2].description == "real description"

    def test_empty_input_returns_empty_list(self):
        results = scrape_batch([], workers=4)
        assert results == []

    def test_single_url(self):
        with patch("src.scrapers.comeet._playwright_scrape", return_value=_job("only one")):
            results = scrape_batch(["https://www.comeet.com/jobs/x/1/eng/X1"], workers=1)
        assert len(results) == 1
        assert results[0].description == "only one"

    def test_more_workers_than_urls_is_fine(self):
        """ThreadPoolExecutor handles workers > len(urls) gracefully."""
        urls = ["https://www.comeet.com/jobs/x/1/eng/X1"]
        with patch("src.scrapers.comeet._playwright_scrape", return_value=_job("ok")):
            results = scrape_batch(urls, workers=20)
        assert results[0].description == "ok"

    def test_all_errors_returns_all_empty(self):
        urls = ["https://www.comeet.com/jobs/a/1/eng/A1", "https://www.comeet.com/jobs/b/1/eng/B1"]
        with patch("src.scrapers.comeet._playwright_scrape", side_effect=RuntimeError("fail")):
            results = scrape_batch(urls, workers=2)
        assert all(r.description == "" for r in results)


# ── search_comeet_companies (parallel) ────────────────────────────────────────

class TestSearchComeetCompaniesParallel:
    def _patch(self, scrape_side_effect):
        """Helper: patch both _load_companies and the underlying scrape_company_page."""
        return (
            patch("src.job_search_comeet._load_companies", return_value=FAKE_COMPANIES),
            patch("src.scrapers.comeet.scrape_company_page", side_effect=scrape_side_effect),
        )

    def test_collects_jobs_from_all_companies(self):
        def _scrape(slug):
            return ACME_JOBS if slug == "acme" else GLOBEX_JOBS

        with patch("src.job_search_comeet._load_companies", return_value=FAKE_COMPANIES), \
             patch("src.scrapers.comeet.scrape_company_page", side_effect=_scrape):
            results = search_comeet_companies(keywords="")

        assert len(results) == len(ACME_JOBS) + len(GLOBEX_JOBS)
        titles = {r["title"] for r in results}
        assert "Computer Vision Engineer" in titles
        assert "Sales Manager" in titles
        assert "Deep Learning Researcher" in titles

    def test_keyword_filtering(self):
        def _scrape(slug):
            return ACME_JOBS if slug == "acme" else GLOBEX_JOBS

        with patch("src.job_search_comeet._load_companies", return_value=FAKE_COMPANIES), \
             patch("src.scrapers.comeet.scrape_company_page", side_effect=_scrape):
            results = search_comeet_companies(keywords="vision")

        # Only "Computer Vision Engineer" contains "vision"
        assert len(results) == 1
        assert results[0]["title"] == "Computer Vision Engineer"

    def test_company_error_doesnt_break_others(self):
        """One failing company page does not block results from the rest."""
        def _scrape(slug):
            if slug == "acme":
                raise RuntimeError("Playwright timeout")
            return GLOBEX_JOBS

        with patch("src.job_search_comeet._load_companies", return_value=FAKE_COMPANIES), \
             patch("src.scrapers.comeet.scrape_company_page", side_effect=_scrape):
            results = search_comeet_companies(keywords="")

        assert any(r["company"] == "Globex" for r in results)
        assert not any(r["company"] == "Acme" for r in results)

    def test_result_shape(self):
        """Each result has the expected keys and values."""
        with patch("src.job_search_comeet._load_companies", return_value=[FAKE_COMPANIES[0]]), \
             patch("src.scrapers.comeet.scrape_company_page", return_value=ACME_JOBS[:1]):
            results = search_comeet_companies(keywords="")

        r = results[0]
        assert r["board"] == "Comeet"
        assert r["company"] == "Acme"
        assert r["title"] == "Computer Vision Engineer"
        assert r["url"] == ACME_JOBS[0]["url"]
        assert r["description"] == ""   # descriptions are fetched later by scrape_url

    def test_empty_company_list(self):
        with patch("src.job_search_comeet._load_companies", return_value=[]):
            results = search_comeet_companies(keywords="")
        assert results == []

    def test_company_with_no_matching_jobs(self):
        """Company returns jobs, but none match the keyword filter."""
        with patch("src.job_search_comeet._load_companies", return_value=[FAKE_COMPANIES[0]]), \
             patch("src.scrapers.comeet.scrape_company_page", return_value=ACME_JOBS):
            results = search_comeet_companies(keywords="robotics")
        assert results == []
