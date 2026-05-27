"""Tests for ingestion.real_ml_loader — parse + validate helpers."""

from __future__ import annotations

import pytest

from ingestion.real_ml_loader import parse_american_odds, validate_row


def test_parse_american_odds_negative():
    assert parse_american_odds("-110") == -110


def test_parse_american_odds_positive():
    assert parse_american_odds("+150") == 150
    assert parse_american_odds("150") == 150


def test_parse_american_odds_blank_returns_none():
    assert parse_american_odds("") is None
    assert parse_american_odds("  ") is None
    assert parse_american_odds(None) is None


def test_parse_american_odds_invalid_raises():
    with pytest.raises(ValueError):
        parse_american_odds("not a number")
    with pytest.raises(ValueError):
        parse_american_odds("-50")  # American odds must be <= -100 or >= +100


def test_validate_row_good():
    row = {
        "season": "2024",
        "week": "1",
        "home_team": "Kansas City Chiefs",
        "away_team": "Baltimore Ravens",
        "ml_home_real": "-180",
        "ml_away_real": "+155",
        "source": "nflverse",
        "source_url": "",
    }
    result = validate_row(row)
    assert result["season"] == 2024
    assert result["week"] == 1
    assert result["ml_home_real"] == -180
    assert result["ml_away_real"] == 155
    assert result["source"] == "nflverse"


def test_validate_row_blank_ml_returns_none_marker():
    row = {
        "season": "2024",
        "week": "3",
        "home_team": "Pittsburgh Steelers",
        "away_team": "Los Angeles Chargers",
        "ml_home_real": "",
        "ml_away_real": "",
        "source": "fixture",
        "source_url": "",
    }
    result = validate_row(row)
    assert result is None  # signals "skip this row"


def test_validate_row_bad_team_raises():
    row = {
        "season": "2024",
        "week": "1",
        "home_team": "Bogus Team",
        "away_team": "Baltimore Ravens",
        "ml_home_real": "-180",
        "ml_away_real": "+155",
        "source": "fixture",
        "source_url": "",
    }
    with pytest.raises(ValueError, match="unknown team"):
        validate_row(row)
