"""Tests for app.this_week_view team-filter helpers (pure, no Streamlit)."""

from __future__ import annotations

from app.this_week_view import board_teams, filter_board, game_teams
from engine.this_week import ThisWeekGame


def _g(matchup: str) -> ThisWeekGame:
    return ThisWeekGame(
        game_key="k", matchup=matchup, commence_time="t",
        cons_spread_home=None, cons_total=None,
        best_spread_home=None, best_spread_away=None,
        best_total_over=None, best_total_under=None,
        best_ml_home=None, best_ml_away=None,
        spread_move=None, total_move=None, spread_ctx=None, total_ctx=None,
    )


def test_game_teams_parses_away_at_home():
    assert game_teams("Buffalo Bills at Kansas City Chiefs") == (
        "Buffalo Bills", "Kansas City Chiefs")


def test_board_teams_sorted_and_unique():
    board = [_g("Buffalo Bills at Kansas City Chiefs"),
             _g("Dallas Cowboys at Buffalo Bills")]
    assert board_teams(board) == ["Buffalo Bills", "Dallas Cowboys", "Kansas City Chiefs"]


def test_filter_board_matches_home_or_away():
    board = [
        _g("Buffalo Bills at Kansas City Chiefs"),   # Bills away
        _g("Dallas Cowboys at Buffalo Bills"),       # Bills home
        _g("Green Bay Packers at Chicago Bears"),
    ]
    bills = filter_board(board, "Buffalo Bills")
    assert len(bills) == 2
    assert all("Buffalo Bills" in g.matchup for g in bills)
    assert filter_board(board, "Chicago Bears") == [board[2]]
