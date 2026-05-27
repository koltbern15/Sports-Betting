"""Loader for real historical moneylines into the real_ml_lines table.

Two layers:
  - pure helpers (parse_american_odds, validate_row) — testable without DB
  - orchestrator (load_csv_to_db) — joins to games, upserts, idempotent
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

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


@dataclass(frozen=True)
class LoadReport:
    """Counts emitted by `load_csv_to_db`."""

    inserted: int
    skipped_blank: int
    rejected_bad: int
    unmatched_games: int
    errors: list[str] = field(default_factory=list)


def load_csv_to_db(conn: sqlite3.Connection, csv_path: str | Path) -> LoadReport:
    """Load real-ML rows from a CSV into `real_ml_lines`. Idempotent."""
    inserted = 0
    skipped_blank = 0
    rejected_bad = 0
    unmatched_games = 0
    errors: list[str] = []
    now_iso = datetime.now(UTC).isoformat(timespec="seconds")

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_no, raw in enumerate(reader, start=2):  # line 1 is header
            try:
                parsed = validate_row(raw)
            except ValueError as e:
                rejected_bad += 1
                errors.append(f"line {line_no}: {e}")
                continue
            if parsed is None:
                skipped_blank += 1
                continue

            cursor = conn.execute(
                "SELECT game_id FROM games"
                " WHERE season=? AND week=? AND home_team=? AND away_team=?",
                (parsed["season"], parsed["week"], parsed["home_team"], parsed["away_team"]),
            )
            match = cursor.fetchone()
            if match is None:
                unmatched_games += 1
                errors.append(
                    f"line {line_no}: no game found for "
                    f"{parsed['season']} W{parsed['week']} "
                    f"{parsed['away_team']} @ {parsed['home_team']}"
                )
                continue
            game_id = match[0]

            conn.execute(
                "INSERT OR REPLACE INTO real_ml_lines"
                "(game_id, ml_home_real, ml_away_real, source, source_url, collected_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    parsed["ml_home_real"],
                    parsed["ml_away_real"],
                    parsed["source"],
                    parsed["source_url"],
                    now_iso,
                ),
            )
            inserted += 1
    conn.commit()

    return LoadReport(
        inserted=inserted,
        skipped_blank=skipped_blank,
        rejected_bad=rejected_bad,
        unmatched_games=unmatched_games,
        errors=errors,
    )


def _main() -> int:
    """CLI: uv run python -m ingestion.real_ml_loader <csv_path>"""
    import sys

    from engine.db import connect, init_schema

    if len(sys.argv) != 2:
        print("Usage: python -m ingestion.real_ml_loader <csv_path>")
        return 2
    csv_path = sys.argv[1]
    conn = connect("data/db/nfl_betting.sqlite")
    init_schema(conn)
    report = load_csv_to_db(conn, csv_path)
    print(
        f"inserted={report.inserted} "
        f"skipped_blank={report.skipped_blank} "
        f"rejected_bad={report.rejected_bad} "
        f"unmatched_games={report.unmatched_games}"
    )
    for err in report.errors[:10]:
        print(f"  {err}")
    if len(report.errors) > 10:
        print(f"  ... ({len(report.errors) - 10} more)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
