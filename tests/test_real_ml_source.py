"""Tests for ingestion.real_ml_source — nflverse fetcher with mocked HTTP."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ingestion.real_ml_source import fetch_real_ml


def _fake_nflverse_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2024, 2024, 2024],
            "week": [1, 1, 2],
            "game_type": ["REG", "REG", "REG"],
            "home_team": ["KC", "BUF", "LV"],
            "away_team": ["BAL", "ARI", "LAC"],
            "home_moneyline": [-180, -240, +145],
            "away_moneyline": [+155, +200, -170],
            "spread_line": [-3.0, -6.5, +3.5],
        }
    )


def test_fetch_real_ml_returns_canonical_columns():
    with patch("ingestion.real_ml_source.nfl.import_schedules", return_value=_fake_nflverse_df()):
        df = fetch_real_ml([2024])
    assert list(df.columns) == [
        "season",
        "week",
        "home_team",
        "away_team",
        "ml_home_real",
        "ml_away_real",
        "source",
    ]
    assert df["source"].unique().tolist() == ["nflverse"]
    assert df.iloc[0]["home_team"] == "Kansas City Chiefs"
    assert df.iloc[0]["away_team"] == "Baltimore Ravens"


def test_fetch_real_ml_drops_rows_with_missing_ml():
    fake = _fake_nflverse_df()
    fake.loc[0, "home_moneyline"] = None
    with patch("ingestion.real_ml_source.nfl.import_schedules", return_value=fake):
        df = fetch_real_ml([2024])
    assert len(df) == 2  # row 0 dropped (missing home_ml)


def test_fetch_real_ml_passes_seasons_to_nflverse():
    captured = {}

    def fake_import(seasons):
        captured["seasons"] = seasons
        return _fake_nflverse_df()

    with patch("ingestion.real_ml_source.nfl.import_schedules", side_effect=fake_import):
        fetch_real_ml([2022, 2023, 2024])
    assert captured["seasons"] == [2022, 2023, 2024]


def test_fetch_real_ml_remaps_playoff_weeks_to_kaggle_convention():
    # nflverse encodes playoff games with game_type WC/DIV/CON/SB and sequential
    # week numbers. Kaggle uses fixed 100-103. fetch_real_ml must remap.
    fake = pd.DataFrame(
        {
            "season": [2024, 2024, 2024, 2024, 2024],
            "week": [18, 19, 20, 21, 22],
            "game_type": ["REG", "WC", "DIV", "CON", "SB"],
            "home_team": ["KC", "BUF", "BAL", "KC", "PHI"],
            "away_team": ["BAL", "ARI", "LAC", "BUF", "KC"],
            "home_moneyline": [-180, -240, -150, -200, -110],
            "away_moneyline": [+155, +200, +130, +170, -110],
            "spread_line": [-3.0, -6.5, -3.5, -4.5, 0.0],
        }
    )
    with patch("ingestion.real_ml_source.nfl.import_schedules", return_value=fake):
        df = fetch_real_ml([2024])
    weeks = df["week"].tolist()
    assert weeks == [18, 100, 101, 102, 103]
