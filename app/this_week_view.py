"""Render the This Week board (thin view over engine.this_week.build_board)."""

from __future__ import annotations

import streamlit as st

from app.theme import HONESTY_BANNER
from engine.this_week import ThisWeekGame


def game_teams(matchup: str) -> tuple[str, str]:
    """Split a 'Away at Home' matchup into (away, home)."""
    away, _, home = matchup.partition(" at ")
    return away, home


def board_teams(board: list[ThisWeekGame]) -> list[str]:
    """Sorted unique team names appearing in this week's slate."""
    return sorted({t for g in board for t in game_teams(g.matchup)})


def filter_board(board: list[ThisWeekGame], team: str) -> list[ThisWeekGame]:
    """Games where `team` is home or away."""
    return [g for g in board if team in game_teams(g.matchup)]


def _fmt_best(b) -> str:
    if b is None:
        return "—"
    book, point, price = b
    sign = "+" if price > 0 else ""
    pt = "" if point is None else f"{point:+g} @ "
    return f"{pt}{sign}{price} ({book})"


def _move_html(move) -> str:
    if move is None:
        return '<span class="twg-ctx">no opener captured yet</span>'
    cls = "twg-move-down" if move < 0 else "twg-move-up"
    arrow = "▼" if move < 0 else "▲"
    return f'<span class="{cls}">{arrow} {move:+g} since open</span>'


def render(board: list[ThisWeekGame]) -> None:
    st.markdown(f'<div class="twg-banner">{HONESTY_BANNER}</div>', unsafe_allow_html=True)
    if not board:
        st.info("No upcoming games / no odds captured yet. Pull odds with "
                "`uv run python -m ingestion.live_odds` (needs ODDS_API_KEY).")
        return
    pick = st.selectbox("Team", ["All teams", *board_teams(board)], key="tw_team")
    games = board if pick == "All teams" else filter_board(board, pick)
    plural = "game" if len(games) == 1 else "games"
    st.caption(f"{len(games)} {plural} · sorted by biggest line move")
    for g in games:
        spread_ctx = (f" · historical home cover: {g.spread_ctx['win_rate']:.1%} "
                      f"(n={g.spread_ctx['n']}, -110, not certified)") if g.spread_ctx else ""
        cs = f"{g.cons_spread_home:+g}" if g.cons_spread_home is not None else "—"
        ct = f"{g.cons_total:g}" if g.cons_total is not None else "—"
        st.markdown(
            f'<div class="twg-card">'
            f'<div class="twg-matchup">{g.matchup}</div>'
            f'<div class="twg-time">{g.commence_time}</div>'
            f'<div style="margin-top:8px">'
            f'<b>Spread</b> (home): consensus {cs} · '
            f'best home <span class="twg-best">{_fmt_best(g.best_spread_home)}</span> · '
            f'best away <span class="twg-best">{_fmt_best(g.best_spread_away)}</span> · '
            f'{_move_html(g.spread_move)}<span class="twg-ctx">{spread_ctx}</span></div>'
            f'<div><b>Total</b>: consensus {ct} · '
            f'best over <span class="twg-best">{_fmt_best(g.best_total_over)}</span> · '
            f'best under <span class="twg-best">{_fmt_best(g.best_total_under)}</span></div>'
            f'<div><b>Moneyline</b>: best home '
            f'<span class="twg-best">{_fmt_best(g.best_ml_home)}</span> · '
            f'best away <span class="twg-best">{_fmt_best(g.best_ml_away)}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
