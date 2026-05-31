from __future__ import annotations

from engine.db import connect, init_schema
from ingestion.live_odds import GameOdds
from ingestion.live_odds_store import current_consensus, opener_consensus, store_snapshot


def _g(spread, total, ml_home=-140, ml_away=120):
    return GameOdds(
        game_key="2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs",
        commence_time="2026-09-07T17:00:00Z",
        home_team="Kansas City Chiefs", away_team="Buffalo Bills",
        cons_spread_home=spread, cons_total=total, cons_ml_home=ml_home, cons_ml_away=ml_away,
        best_spread_home=None, best_spread_away=None, best_total_over=None,
        best_total_under=None, best_ml_home=None, best_ml_away=None, n_books=3,
    )


def test_store_and_read_opener_vs_current():
    conn = connect(":memory:")
    init_schema(conn)
    store_snapshot(conn, [_g(-2.5, 48.5)], captured_at="2026-09-03T12:00:00Z")
    store_snapshot(conn, [_g(-4.0, 49.5)], captured_at="2026-09-06T12:00:00Z")
    key = "2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs"
    op = opener_consensus(conn)[key]
    cur = current_consensus(conn)[key]
    assert op["cons_spread_home"] == -2.5   # earliest
    assert cur["cons_spread_home"] == -4.0  # latest
    conn.close()


def test_store_returns_count():
    conn = connect(":memory:")
    init_schema(conn)
    n = store_snapshot(conn, [_g(-2.5, 48.5)], captured_at="2026-09-03T12:00:00Z")
    assert n == 1
    conn.close()
