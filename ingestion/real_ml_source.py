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


def fetch_real_ml(seasons: list[int]) -> pd.DataFrame:
    """Fetch real historical moneylines for the given seasons.

    Returns a DataFrame with columns:
        season (int), week (int),
        home_team (canonical full name), away_team (canonical full name),
        ml_home_real (int), ml_away_real (int),
        source (str = "nflverse")

    Rows missing either moneyline are dropped.
    """
    raw = nfl.import_schedules(seasons)
    df = raw[["season", "week", "home_team", "away_team", COL_HOME_ML, COL_AWAY_ML]].copy()
    df = df.dropna(subset=[COL_HOME_ML, COL_AWAY_ML])
    df["home_team"] = df["home_team"].map(code_to_canonical)
    df["away_team"] = df["away_team"].map(code_to_canonical)
    df = df.rename(columns={COL_HOME_ML: "ml_home_real", COL_AWAY_ML: "ml_away_real"})
    df["ml_home_real"] = df["ml_home_real"].astype(int)
    df["ml_away_real"] = df["ml_away_real"].astype(int)
    df["source"] = "nflverse"
    return df[
        ["season", "week", "home_team", "away_team", "ml_home_real", "ml_away_real", "source"]
    ].reset_index(drop=True)
