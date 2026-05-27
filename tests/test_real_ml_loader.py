"""Tests for ingestion.real_ml_loader — parse + validate helpers."""

from __future__ import annotations

import sqlite3

import pytest

from engine.db import init_schema
from ingestion.real_ml_loader import LoadReport, load_csv_to_db, parse_american_odds, validate_row


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


def _seed_games(conn: sqlite3.Connection) -> None:
    rows = [
        ("2024_01_KC_BAL", 2024, 1, "2024-09-05", "Kansas City Chiefs", "Baltimore Ravens"),
        ("2024_01_BUF_ARI", 2024, 1, "2024-09-08", "Buffalo Bills", "Arizona Cardinals"),
        ("2024_02_DET_TB", 2024, 2, "2024-09-15", "Detroit Lions", "Tampa Bay Buccaneers"),
        ("2024_02_GB_IND", 2024, 2, "2024-09-15", "Green Bay Packers", "Indianapolis Colts"),
        ("2024_03_PIT_LAC", 2024, 3, "2024-09-22", "Pittsburgh Steelers", "Los Angeles Chargers"),
    ]
    conn.executemany(
        "INSERT INTO games(game_id, season, week, game_date, home_team, away_team)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def test_load_csv_to_db_happy_path(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_games(conn)

    report = load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")

    assert isinstance(report, LoadReport)
    assert report.inserted == 4  # row 5 has blank ML, skipped
    assert report.skipped_blank == 1
    assert report.rejected_bad == 0
    assert report.unmatched_games == 0

    cursor = conn.execute("SELECT COUNT(*) FROM real_ml_lines")
    assert cursor.fetchone()[0] == 4
    conn.close()


def test_load_csv_to_db_idempotent(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_games(conn)

    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")  # second run

    cursor = conn.execute("SELECT COUNT(*) FROM real_ml_lines")
    assert cursor.fetchone()[0] == 4  # still 4, not 8
    conn.close()


def test_load_csv_to_db_unmatched_games_reported(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    # seed only 2 of the 5 fixture games
    conn.executemany(
        "INSERT INTO games(game_id, season, week, game_date, home_team, away_team)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("2024_01_KC_BAL", 2024, 1, "2024-09-05", "Kansas City Chiefs", "Baltimore Ravens"),
            ("2024_01_BUF_ARI", 2024, 1, "2024-09-08", "Buffalo Bills", "Arizona Cardinals"),
        ],
    )
    conn.commit()

    report = load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")

    assert report.inserted == 2
    assert report.unmatched_games == 2  # Detroit + Green Bay; row 5 was blank so skipped first
    conn.close()
