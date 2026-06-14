"""Leans tab — honest per-game spread/total reads (thin view over engine.leans)."""

from __future__ import annotations

import streamlit as st

from app.this_week_view import _fmt_best
from engine.leans import MarketLean, RatesMap, game_leans
from engine.this_week import ThisWeekGame

_BANNER = (
    "<b>Leans, not picks.</b> Each read shows the historically-favored side ONLY when its "
    "bucket cleared the -110 breakeven (52.4%) with a real sample over the selected seasons "
    "— otherwise 'no lean'. The static buckets are noise, so this is historical context plus "
    "the best available price, never a prediction. Gamble responsibly."
)


def _lean_headline(ml: MarketLean) -> str:
    """One-line human summary of a MarketLean. Pure (no Streamlit)."""
    if ml.state == "no_line":
        return f"{ml.market.title()}: no consensus line posted yet"
    if ml.state == "no_data":
        return f"{ml.market.title()}: no historical data for this bucket in range"
    if ml.state == "lean":
        return (
            f"LEAN: {ml.side_label} — {ml.rate:.1%} historically (n={ml.n}), "
            "clears the -110 breakeven; context, not a pick"
        )
    return f"No lean — coin flip ({ml.rate:.1%}, n={ml.n})"


def _price_line(ml: MarketLean) -> str:
    if ml.state == "lean":
        return f"→ Best price: {_fmt_best(ml.best_for_lean)}"
    primary, secondary = ("over", "under") if ml.market == "total" else ("home", "away")
    return (
        f"→ best {primary} {_fmt_best(ml.best_primary)} · "
        f"best {secondary} {_fmt_best(ml.best_secondary)}"
    )


def _market_row(label: str, ml: MarketLean) -> str:
    """HTML for one market row. Price line is omitted only when there is no line."""
    head = _lean_headline(ml)
    price = "" if ml.state == "no_line" else (
        f'<br><span class="twg-ctx">{_price_line(ml)}</span>'
    )
    return f'<div style="margin-top:8px"><b>{label}</b> — {head}{price}</div>'


def render(
    board: list[ThisWeekGame], spread_rates: RatesMap, total_rates: RatesMap
) -> None:
    st.markdown(f'<div class="twg-banner">{_BANNER}</div>', unsafe_allow_html=True)
    if not board:
        st.info(
            "No upcoming games / no odds captured yet. Pull odds with "
            "`uv run python -m ingestion.live_odds` (needs ODDS_API_KEY)."
        )
        return
    st.caption(
        "Leans reflect the season range in the sidebar — narrowing it shrinks samples, "
        "so more games show 'no lean'."
    )
    for g in board:
        sp, tot = game_leans(g, spread_rates, total_rates)
        st.markdown(
            f'<div class="twg-card"><div class="twg-matchup">{g.matchup}</div>'
            f'<div class="twg-time">{g.commence_time}</div>'
            f'{_market_row("Spread", sp)}{_market_row("Total", tot)}</div>',
            unsafe_allow_html=True,
        )
