"""Tier-1 real moneyline data source — nflverse via nfl_data_py.

Wraps `nfl_data_py.import_schedules()` and normalizes its output to the
canonical schema consumed by `ingestion.real_ml_loader`. If T1 probe found
different column names, update the COL_HOME_ML / COL_AWAY_ML constants.
"""

from __future__ import annotations

import nfl_data_py as nfl
import pandas as pd

from ingestion.team_codes import code_to_canonical

COL_HOME_ML = "home_moneyline"
COL_AWAY_ML = "away_moneyline"

# nflverse encodes playoff games with sequential week numbers (18-22, depending
# on season length). Kaggle's `ingestion.loader._PLAYOFF_WEEK_MAP` remaps the
# same games to fixed weeks 100-103 keyed by round. Use nflverse's `game_type`
# to align with Kaggle's convention so `real_ml_loader` can join.
_PLAYOFF_TYPE_TO_WEEK: dict[str, int] = {
    "WC": 100,   # Wild Card
    "DIV": 101,  # Divisional
    "CON": 102,  # Conference Championship
    "SB": 103,   # Super Bowl
}


def _remap_playoff_week(game_type: str, week: int) -> int:
    """Map nflverse (game_type, week) -> Kaggle-compatible integer week."""
    if game_type == "REG":
        return week
    return _PLAYOFF_TYPE_TO_WEEK.get(game_type, week)


def fetch_real_ml(seasons: list[int]) -> pd.DataFrame:
    """Fetch real historical moneylines for the given seasons.

    Returns a DataFrame with columns:
        season (int), week (int),
        home_team (canonical full name), away_team (canonical full name),
        ml_home_real (int), ml_away_real (int),
        source (str = "nflverse")

    Rows missing either moneyline are dropped. Playoff weeks are remapped from
    nflverse's sequential integers to Kaggle's 100-103 convention so the loader
    can join to the existing games table.
    """
    raw = nfl.import_schedules(seasons)
    df = raw[
        ["season", "week", "game_type", "home_team", "away_team", COL_HOME_ML, COL_AWAY_ML]
    ].copy()
    df = df.dropna(subset=[COL_HOME_ML, COL_AWAY_ML])
    df["home_team"] = df["home_team"].map(code_to_canonical)
    df["away_team"] = df["away_team"].map(code_to_canonical)
    df["week"] = [
        _remap_playoff_week(gt, int(w))
        for gt, w in zip(df["game_type"], df["week"], strict=True)
    ]
    df = df.rename(columns={COL_HOME_ML: "ml_home_real", COL_AWAY_ML: "ml_away_real"})
    df["ml_home_real"] = df["ml_home_real"].astype(int)
    df["ml_away_real"] = df["ml_away_real"].astype(int)
    df["source"] = "nflverse"
    return df[
        ["season", "week", "home_team", "away_team", "ml_home_real", "ml_away_real", "source"]
    ].reset_index(drop=True)
