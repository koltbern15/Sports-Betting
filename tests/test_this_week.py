from __future__ import annotations

from engine.this_week import build_board, historical_spread_context


def test_historical_spread_context_looks_up_bucket():
    ctx = historical_spread_context(-3.0)
    # uses committed ats_by_bucket.csv; either a valid context dict or None (if file/bucket absent)
    assert ctx is None or (0.0 <= ctx["win_rate"] <= 1.0 and ctx["n"] > 0 and "bucket" in ctx)


def test_build_board_movement_and_best_price():
    games = [_make_game(cons_spread_home=-4.0, best_ml_home=("DK", None, -140))]
    openers = {games[0].game_key: {"cons_spread_home": -2.5, "cons_total": 48.0}}
    board = build_board(games, openers)
    assert len(board) == 1
    g = board[0]
    assert g.spread_move == -1.5            # current -4.0 - opener -2.5
    assert g.best_ml_home == ("DK", None, -140)
    assert g.matchup == "Buffalo Bills at Kansas City Chiefs"


def test_build_board_no_opener_yields_none_movement():
    games = [_make_game(cons_spread_home=-4.0)]
    board = build_board(games, openers={})
    assert board[0].spread_move is None


def test_build_board_empty():
    assert build_board([], {}) == []


def test_build_board_sorted_by_abs_spread_move_desc():
    g_small = _make_game(cons_spread_home=-3.0)          # move 0 vs opener -3.0
    g_big = _make_game(cons_spread_home=-7.0, key="k2")  # move -4 vs opener -3.0
    openers = {g_small.game_key: {"cons_spread_home": -3.0},
               g_big.game_key: {"cons_spread_home": -3.0}}
    board = build_board([g_small, g_big], openers)
    assert board[0].game_key == "k2"  # bigger absolute move first


def _make_game(cons_spread_home=-3.0, cons_total=47.0, best_ml_home=None, key=None):
    from ingestion.live_odds import GameOdds
    return GameOdds(
        game_key=key or "2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs",
        commence_time="2026-09-07T17:00:00Z",
        home_team="Kansas City Chiefs", away_team="Buffalo Bills",
        cons_spread_home=cons_spread_home, cons_total=cons_total,
        cons_ml_home=-140, cons_ml_away=120,
        best_spread_home=("DK", cons_spread_home, -110),
        best_spread_away=("FD", -cons_spread_home, -110),
        best_total_over=("DK", cons_total, -110), best_total_under=("FD", cons_total, -110),
        best_ml_home=best_ml_home, best_ml_away=("FD", None, 120), n_books=3,
    )
