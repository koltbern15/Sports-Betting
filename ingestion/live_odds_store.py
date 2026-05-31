"""Persist live-odds consensus snapshots and read opener (earliest) / current (latest)."""

from __future__ import annotations

import sqlite3

from ingestion.live_odds import GameOdds


def store_snapshot(conn: sqlite3.Connection, games: list[GameOdds], *, captured_at: str) -> int:
    """Insert one consensus row per game for this capture. Returns rows inserted."""
    n = 0
    for g in games:
        conn.execute(
            "INSERT INTO live_odds_snapshots"
            " (captured_at, game_key, commence_time, home_team, away_team,"
            "  cons_spread_home, cons_total, cons_ml_home, cons_ml_away)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (captured_at, g.game_key, g.commence_time, g.home_team, g.away_team,
             g.cons_spread_home, g.cons_total, g.cons_ml_home, g.cons_ml_away),
        )
        n += 1
    conn.commit()
    return n


def _consensus(conn: sqlite3.Connection, *, newest: bool) -> dict[str, dict]:
    order = "DESC" if newest else "ASC"
    rows = conn.execute(
        f"SELECT game_key, captured_at, commence_time, home_team, away_team,"
        f" cons_spread_home, cons_total, cons_ml_home, cons_ml_away"
        f" FROM live_odds_snapshots ORDER BY captured_at {order}"
    ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        key = r[0]
        if key in out:
            continue  # first seen wins (newest or earliest per `order`)
        out[key] = {
            "captured_at": r[1], "commence_time": r[2],
            "home_team": r[3], "away_team": r[4],
            "cons_spread_home": r[5], "cons_total": r[6],
            "cons_ml_home": r[7], "cons_ml_away": r[8],
        }
    return out


def opener_consensus(conn: sqlite3.Connection) -> dict[str, dict]:
    """Earliest stored consensus per game (our captured 'open')."""
    return _consensus(conn, newest=False)


def current_consensus(conn: sqlite3.Connection) -> dict[str, dict]:
    """Latest stored consensus per game."""
    return _consensus(conn, newest=True)
