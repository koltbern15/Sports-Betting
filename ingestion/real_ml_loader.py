"""Loader for real historical moneylines into the real_ml_lines table.

Two layers:
  - pure helpers (parse_american_odds, validate_row) — testable without DB
  - orchestrator (load_csv_to_db) — joins to games, upserts, idempotent

This file only contains the pure helpers; the orchestrator is added in T7.
"""

from __future__ import annotations

from ingestion.team_names import CANONICAL_TEAMS


def parse_american_odds(value: str | None) -> int | None:
    """Parse a string American-odds value to int, or None if blank.

    Raises ValueError if value is non-blank and not a valid American odds magnitude
    (i.e., must satisfy |x| >= 100).
    """
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    try:
        n = int(stripped)
    except ValueError as e:
        raise ValueError(f"not a valid American odds value: {value!r}") from e
    if -100 < n < 100:
        raise ValueError(f"American odds magnitude must be >= 100, got {n}")
    return n


def validate_row(row: dict) -> dict | None:
    """Validate + coerce a CSV row. Returns parsed dict, or None if blank ML pair.

    Raises ValueError for malformed data (bad team name, bad number formats).
    """
    home_ml = parse_american_odds(row.get("ml_home_real"))
    away_ml = parse_american_odds(row.get("ml_away_real"))
    if home_ml is None and away_ml is None:
        return None
    home_team = row["home_team"].strip()
    away_team = row["away_team"].strip()
    if home_team not in CANONICAL_TEAMS:
        raise ValueError(f"unknown team: {home_team!r}")
    if away_team not in CANONICAL_TEAMS:
        raise ValueError(f"unknown team: {away_team!r}")
    return {
        "season": int(row["season"]),
        "week": int(row["week"]),
        "home_team": home_team,
        "away_team": away_team,
        "ml_home_real": home_ml,
        "ml_away_real": away_ml,
        "source": row.get("source", "").strip() or "unknown",
        "source_url": row.get("source_url", "").strip() or None,
    }
