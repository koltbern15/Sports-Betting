"""CSV → SQLite loader for NFL betting data.

Pure derivation helpers are exported individually for unit testing.
The end-to-end orchestrator is ``load_csv_to_db``.
"""

from __future__ import annotations

import logging
import math
import sys
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

import pandas as pd

from engine.db import connect, init_schema
from ingestion.divisions import same_division
from ingestion.stadiums import is_dome
from ingestion.team_names import canonicalize_team_name


def derive_spread_home_close(
    spread_favorite: float | None,
    favorite_is_home: bool,
) -> float | None:
    """Convert (magnitude, favorite-is-home) to a home-perspective signed spread.

    Output convention:
      - negative = home favored
      - positive = home underdog
      - 0        = pick'em
      - None     = data missing
    """
    is_nan = isinstance(spread_favorite, float) and math.isnan(spread_favorite)
    if spread_favorite is None or is_nan:
        return None
    magnitude = abs(spread_favorite)
    return -magnitude if favorite_is_home else magnitude


def derive_ats_result(
    home_score: int | None,
    away_score: int | None,
    spread_home_close: float | None,
) -> str | None:
    """Compute home-side ATS result.

    Adjusts the home margin by the spread (negative = home favored).
    Returns 'cover' if adjusted > 0, 'loss' if < 0, 'push' if == 0.
    Returns None if any input is missing.
    """
    if home_score is None or away_score is None or spread_home_close is None:
        return None
    home_margin = home_score - away_score
    adjusted = home_margin + spread_home_close
    if adjusted > 0:
        return "cover"
    if adjusted < 0:
        return "loss"
    return "push"


def derive_total_result(
    home_score: int | None,
    away_score: int | None,
    total_close: float | None,
) -> str | None:
    """Compute over/under/push for the combined score vs the total line."""
    if home_score is None or away_score is None or total_close is None:
        return None
    combined = home_score + away_score
    if combined > total_close:
        return "over"
    if combined < total_close:
        return "under"
    return "push"


_PLAYOFF_WEEK_MAP: dict[str, int] = {
    "Wildcard": 100,
    "Division": 101,
    "Conference": 102,
    "Superbowl": 103,
}


def parse_week(raw: str | int) -> int:
    """Map Kaggle's schedule_week values to integer weeks.

    Regular season "1"–"18" → integer; playoff strings → 100–103.
    """
    if isinstance(raw, int):
        return raw
    if raw in _PLAYOFF_WEEK_MAP:
        return _PLAYOFF_WEEK_MAP[raw]
    try:
        return int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Unknown schedule_week value: {raw!r}") from e


def derive_division_game_flag(home_team: str, away_team: str) -> int:
    """1 if the two teams are in the same division, else 0.

    Both inputs must be canonical team names. Caller is responsible for
    running them through ingestion.team_names.canonicalize_team_name first.
    """
    return 1 if same_division(home_team, away_team) else 0


_PRIMETIME_WEEKDAYS: set[int] = {0, 3, 5}  # Monday=0, Thursday=3, Saturday=5


def derive_primetime_flag(game_date: _date, playoff: bool) -> int:
    """Coarse primetime heuristic for the regular season.

    Monday, Thursday, and Saturday regular-season games are treated as primetime.
    Sunday Night Football is NOT captured by this heuristic (no time data in
    the source CSV) and is therefore under-counted. Slice 2 refines this.

    Playoff games always return 0 here; downstream code should branch on
    playoff_flag rather than primetime_flag for playoff analyses.
    """
    if playoff:
        return 0
    return 1 if game_date.weekday() in _PRIMETIME_WEEKDAYS else 0


_log = logging.getLogger(__name__)


@dataclass
class LoadReport:
    rows_read: int = 0
    rows_inserted: int = 0
    rows_skipped_missing_score: int = 0
    rows_skipped_missing_spread: int = 0
    by_season: dict[int, int] = field(default_factory=dict)


def _resolve_favorite_is_home(team_favorite_id: str, home_team: str) -> bool:
    """Kaggle's team_favorite_id is a short code (e.g. 'KAN', 'GB') or 'PICK'."""
    code_to_team = {
        "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
        "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
        "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
        "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
        "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
        "KC": "Kansas City Chiefs", "KAN": "Kansas City Chiefs",
        "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
        "LV": "Las Vegas Raiders", "LVR": "Las Vegas Raiders",
        "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings", "NE": "New England Patriots",
        "NO": "New Orleans Saints", "NYG": "New York Giants", "NYJ": "New York Jets",
        "OAK": "Las Vegas Raiders",
        "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
        "SD": "Los Angeles Chargers", "SDG": "Los Angeles Chargers",
        "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "SFO": "San Francisco 49ers",
        "STL": "Los Angeles Rams",
        "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
        "WAS": "Washington Commanders",
    }
    if team_favorite_id == "PICK":
        return False
    if team_favorite_id not in code_to_team:
        raise ValueError(f"Unknown team_favorite_id: {team_favorite_id!r}")
    return code_to_team[team_favorite_id] == home_team


def _to_int_or_none(x) -> int | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return int(x)


def _to_float_or_none(x) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return float(x)


def _make_game_id(season: int, week: int, away: str, home: str) -> str:
    away_slug = away.replace(" ", "_").replace(".", "")
    home_slug = home.replace(" ", "_").replace(".", "")
    return f"{season}_{week}_{away_slug}_{home_slug}"


def load_csv_to_db(
    csv_path: str | Path,
    db_path: str | Path,
    season_min: int = 2004,
    season_max: int = 2024,
) -> LoadReport:
    """Read the Kaggle spreadspoke_scores CSV, derive Slice-1 fields, write to SQLite.

    Idempotent: re-running with the same CSV produces the same DB state.
    """
    csv_path = Path(csv_path)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    report = LoadReport(rows_read=len(df))

    df = df[(df["schedule_season"] >= season_min) & (df["schedule_season"] <= season_max)].copy()

    conn = connect(db_path)
    try:
        init_schema(conn)
        for _, row in df.iterrows():
            season = int(row["schedule_season"])
            week = parse_week(row["schedule_week"])
            game_date = pd.to_datetime(row["schedule_date"]).date()
            home = canonicalize_team_name(row["team_home"])
            away = canonicalize_team_name(row["team_away"])
            home_score = _to_int_or_none(row["score_home"])
            away_score = _to_int_or_none(row["score_away"])

            spread_favorite = _to_float_or_none(row["spread_favorite"])
            favorite_is_home = _resolve_favorite_is_home(str(row["team_favorite_id"]), home)
            spread_home_close = derive_spread_home_close(spread_favorite, favorite_is_home)

            total_close = _to_float_or_none(row["over_under_line"])
            home_spread_result = derive_ats_result(home_score, away_score, spread_home_close)
            total_result = derive_total_result(home_score, away_score, total_close)

            playoff = str(row["schedule_playoff"]).upper() == "TRUE"
            primetime = derive_primetime_flag(game_date, playoff)
            division_flag = derive_division_game_flag(home, away)
            stadium = row["stadium"] if pd.notna(row["stadium"]) else None
            dome = 1 if is_dome(stadium) else 0

            game_id = _make_game_id(season, week, away, home)

            conn.execute(
                """INSERT OR REPLACE INTO games(
                    game_id, season, week, game_date, home_team, away_team,
                    home_score, away_score, stadium, dome_flag,
                    weather_temp, weather_wind, weather_humidity,
                    primetime_flag, playoff_flag, division_game_flag
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    game_id, season, week, game_date.isoformat(), home, away,
                    home_score, away_score, stadium, dome,
                    _to_int_or_none(row.get("weather_temperature")),
                    _to_int_or_none(row.get("weather_wind_mph")),
                    _to_int_or_none(row.get("weather_humidity")),
                    primetime, int(playoff), division_flag,
                ),
            )
            conn.execute("DELETE FROM betting_lines WHERE game_id = ?", (game_id,))
            conn.execute(
                """INSERT INTO betting_lines(
                    game_id, spread_home_close, total_close,
                    home_spread_result, total_result
                ) VALUES (?,?,?,?,?)""",
                (game_id, spread_home_close, total_close, home_spread_result, total_result),
            )

            report.rows_inserted += 1
            report.by_season[season] = report.by_season.get(season, 0) + 1
            if home_score is None or away_score is None:
                report.rows_skipped_missing_score += 1
            if spread_home_close is None:
                report.rows_skipped_missing_spread += 1

        conn.commit()
    finally:
        conn.close()

    _log.info(
        "Loaded %d rows from %s into %s (seasons %d-%d)",
        report.rows_inserted, csv_path, db_path, season_min, season_max,
    )
    return report


def _main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if len(argv) < 2:
        print("usage: python -m ingestion.loader <path/to/spreadspoke_scores.csv>", file=sys.stderr)
        return 2
    csv_path = Path(argv[1])
    db_path = Path("data/db/nfl_betting.sqlite")
    report = load_csv_to_db(csv_path, db_path)
    print(f"Read:      {report.rows_read}")
    print(f"Inserted:  {report.rows_inserted}")
    print(f"By season: {dict(sorted(report.by_season.items()))}")
    print(f"Missing scores  in inserted rows: {report.rows_skipped_missing_score}")
    print(f"Missing spreads in inserted rows: {report.rows_skipped_missing_spread}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
