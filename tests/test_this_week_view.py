"""Tests for app.this_week_view team-filter helpers (pure, no Streamlit)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.this_week_view import _humanize_ago, board_teams, filter_board, game_teams
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


def _render_none_consensus_script():
    """Self-contained Streamlit script: build a board with no consensus
    spread/total and call render(). AppTest re-executes this source in a fresh
    namespace, so it must import everything it needs itself."""
    from app.this_week_view import render
    from engine.this_week import ThisWeekGame

    game = ThisWeekGame(
        game_key="k", matchup="Buffalo Bills at Kansas City Chiefs", commence_time="t",
        cons_spread_home=None, cons_total=None,
        best_spread_home=None, best_spread_away=None,
        best_total_over=None, best_total_under=None,
        best_ml_home=None, best_ml_away=None,
        spread_move=None, total_move=None, spread_ctx=None, total_ctx=None,
    )
    render([game])


def test_render_handles_none_consensus_without_crashing():
    """Regression: a game with no consensus spread/total (cons_spread_home /
    cons_total = None) must not crash render() via NoneType.__format__."""
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    at = AppTest.from_function(_render_none_consensus_script, default_timeout=30).run()
    assert not at.exception  # render built the HTML without raising
    # The em-dash fallback appears where consensus spread/total would be.
    assert any("—" in md.value for md in at.markdown)


def test_humanize_ago_buckets():
    now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=UTC)
    assert _humanize_ago(now, now) == "just now"
    assert _humanize_ago(datetime(2026, 9, 13, 11, 58, tzinfo=UTC), now) == "~2 minutes ago"
    assert _humanize_ago(datetime(2026, 9, 13, 11, 59, tzinfo=UTC), now) == "~1 minute ago"
    assert _humanize_ago(datetime(2026, 9, 13, 11, 0, tzinfo=UTC), now) == "~1 hour ago"
    assert _humanize_ago(datetime(2026, 9, 13, 8, 0, tzinfo=UTC), now) == "~4 hours ago"
    assert _humanize_ago(datetime(2026, 9, 11, 12, 0, tzinfo=UTC), now) == "~2 days ago"
    # Clock skew (then in the future) clamps to "just now".
    assert _humanize_ago(datetime(2026, 9, 13, 12, 5, tzinfo=UTC), now) == "just now"
