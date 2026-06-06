"""Tests for src/scrapers/date_utils.py"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.date_utils import is_stale, parse_relative_date


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _days_ago(n):
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


# ── parse_relative_date ────────────────────────────────────────────────────────

def test_parse_days_ago():
    result = parse_relative_date("5 days ago")
    assert result == _days_ago(5)


def test_parse_posted_days_ago_capitalised():
    result = parse_relative_date("Posted 3 Days Ago")
    assert result == _days_ago(3)


def test_parse_weeks_ago():
    result = parse_relative_date("2 weeks ago")
    assert result == _days_ago(14)


def test_parse_months_ago():
    result = parse_relative_date("3 months ago")
    assert result == _days_ago(90)


def test_parse_hours_ago_returns_recent():
    result = parse_relative_date("17 hours ago")
    assert result in (_today(), _days_ago(1))


def test_parse_yesterday():
    result = parse_relative_date("yesterday")
    assert result == _days_ago(1)


def test_parse_today():
    result = parse_relative_date("today")
    assert result == _today()


def test_parse_iso_timestamp():
    result = parse_relative_date("2025-04-12T08:30:00Z")
    assert result == "2025-04-12"


def test_parse_empty_string():
    assert parse_relative_date("") == ""


def test_parse_unrecognised_text():
    assert parse_relative_date("soon™") == ""


def test_parse_years_ago():
    result = parse_relative_date("1 year ago")
    assert result == _days_ago(365)


# ── is_stale ──────────────────────────────────────────────────────────────────

def test_is_stale_old_date():
    old = _days_ago(200)
    assert is_stale(old, max_days=180) is True


def test_is_stale_recent_date():
    recent = _days_ago(30)
    assert is_stale(recent, max_days=180) is False


def test_is_stale_exactly_at_threshold_is_not_stale():
    exactly = _days_ago(180)
    assert is_stale(exactly, max_days=180) is False


def test_is_stale_empty_date_returns_false():
    assert is_stale("", max_days=180) is False


def test_is_stale_unknown_format_returns_false():
    assert is_stale("not-a-date", max_days=180) is False
