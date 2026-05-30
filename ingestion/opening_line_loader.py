"""Load OpeningLineRecords into the opening_lines table.

Joins each record to games on (season, home_team, away_team), disambiguating the
rare repeat matchup by game_date. Stores one row per (game_id, source) — both
sources coexist for cross-validation. Idempotent via INSERT OR REPLACE.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ingestion.opening_line_common import OpeningLineRecord


@dataclass(frozen=True)
class OpeningLoadReport:
    inserted: int
    unmatched: int
    errors: list[str] = field(default_factory=list)


def _find_game_id(conn: sqlite3.Connection, rec: OpeningLineRecord) -> str | None:
    """Return the matching game_id, or None. Disambiguate repeats by game_date."""
    rows = conn.execute(
        "SELECT game_id, game_date FROM games"
        " WHERE season=? AND home_team=? AND away_team=?",
        (rec.season, rec.home_team, rec.away_team),
    ).fetchall()
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0][0]
    for game_id, game_date in rows:
        if game_date == rec.game_date:
            return game_id
    return None


def load_records(
    conn: sqlite3.Connection, records: list[OpeningLineRecord]
) -> OpeningLoadReport:
    """Insert records into opening_lines. Idempotent. Unmatched are counted, not inserted."""
    inserted = 0
    unmatched = 0
    errors: list[str] = []
    now_iso = datetime.now(UTC).isoformat(timespec="seconds")

    for rec in records:
        game_id = _find_game_id(conn, rec)
        if game_id is None:
            unmatched += 1
            errors.append(
                f"no game for {rec.season} {rec.away_team} @ {rec.home_team} ({rec.game_date})"
            )
            continue
        conn.execute(
            "INSERT OR REPLACE INTO opening_lines"
            " (game_id, source, open_spread_home, open_total, open_ml_home,"
            "  open_ml_away, source_url, collected_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                game_id, rec.source, rec.open_spread_home, rec.open_total,
                rec.open_ml_home, rec.open_ml_away, rec.source_url, now_iso,
            ),
        )
        inserted += 1
    conn.commit()
    return OpeningLoadReport(inserted=inserted, unmatched=unmatched, errors=errors)


def canonical_opener_source(season: int) -> str:
    """Documented precedence for the canonical opener per season.

    2007-2012: only SBR has data. 2013+: prefer aussportsbetting (richer source,
    spread+total+ML opening). In the 2013-2021 overlap SBR is retained as the
    cross-check counterpart but 'aus' is canonical. Tunable after the audit.
    """
    return "sbr" if season <= 2012 else "aus"
