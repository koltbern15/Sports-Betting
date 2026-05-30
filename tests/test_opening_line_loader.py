"""Tests for ingestion.opening_line_loader — join + insert vs in-memory DB."""

from __future__ import annotations

from engine.db import connect, init_schema
from ingestion.opening_line_common import OpeningLineRecord
from ingestion.opening_line_loader import (
    canonical_opener_source,
    load_records,
)


def _seed_game(conn, game_id, season, week, date, home, away):
    conn.execute(
        "INSERT INTO games (game_id, season, week, game_date, home_team, away_team)"
        " VALUES (?,?,?,?,?,?)",
        (game_id, season, week, date, home, away),
    )


def _rec(season, date, home, away, source, spread=-3.0, total=47.0):
    return OpeningLineRecord(
        season=season, game_date=date, home_team=home, away_team=away,
        open_spread_home=spread, open_total=total, open_ml_home=None,
        open_ml_away=None, source=source, source_url="http://x",
    )


def test_load_matches_on_season_home_away():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    report = load_records(
        conn, [_rec(2015, "2015-09-13", "Dallas Cowboys", "New York Giants", "sbr")]
    )
    assert report.inserted == 1
    assert report.unmatched == 0
    row = conn.execute(
        "SELECT open_spread_home, source FROM opening_lines WHERE game_id='g1'"
    ).fetchone()
    assert row[0] == -3.0 and row[1] == "sbr"
    conn.close()


def test_two_sources_coexist():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    load_records(conn, [
        _rec(2015, "2015-09-13", "Dallas Cowboys", "New York Giants", "sbr", spread=-3.0),
        _rec(2015, "2015-09-13", "Dallas Cowboys", "New York Giants", "aus", spread=-3.5),
    ])
    n = conn.execute("SELECT COUNT(*) FROM opening_lines WHERE game_id='g1'").fetchone()[0]
    assert n == 2
    conn.close()


def test_unmatched_record_is_counted_not_inserted():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    report = load_records(
        conn, [_rec(2015, "2015-09-20", "Green Bay Packers", "Chicago Bears", "sbr")]
    )
    assert report.inserted == 0
    assert report.unmatched == 1
    conn.close()


def test_repeat_matchup_disambiguated_by_date():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    _seed_game(conn, "g2", 2015, 12, "2015-12-06", "Dallas Cowboys", "New York Giants")
    report = load_records(
        conn, [_rec(2015, "2015-12-06", "Dallas Cowboys", "New York Giants", "sbr")]
    )
    assert report.inserted == 1
    gid = conn.execute("SELECT game_id FROM opening_lines").fetchone()[0]
    assert gid == "g2"
    conn.close()


def test_idempotent_reload():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    rec = _rec(2015, "2015-09-13", "Dallas Cowboys", "New York Giants", "sbr")
    load_records(conn, [rec])
    load_records(conn, [rec])
    n = conn.execute("SELECT COUNT(*) FROM opening_lines").fetchone()[0]
    assert n == 1
    conn.close()


def test_canonical_opener_source_precedence():
    assert canonical_opener_source(2010) == "sbr"
    assert canonical_opener_source(2018) == "aus"
    assert canonical_opener_source(2023) == "aus"
