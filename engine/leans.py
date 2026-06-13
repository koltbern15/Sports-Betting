"""Per-game honest 'leans': a directional read from the historical buckets, gated
at the -110 breakeven, paired with the best available price. Pure, no Streamlit.

A side is named ONLY when its historical bucket rate (over the selected seasons)
clears the -110 breakeven (52.38%) AND n >= 50; otherwise 'no lean'. This is
context + best price, NOT a prediction — the static buckets are noise (see the
Finding tab). Moneyline is excluded (its historical data is derived/biased).
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.ats import bucket_spread
from engine.bucket_analysis import INSUFFICIENT_SAMPLE_THRESHOLD
from engine.stats_utils import BREAKEVEN_AT_NEG_110
from engine.this_week import ThisWeekGame
from engine.totals import bucket_total
from ingestion.live_odds import BestLine

# A rates map is {bucket_name: {"win_rate": float, "n": int}} for the selected
# seasons. Spread win_rate = home cover rate; total win_rate = over rate.
RatesMap = dict[str, dict]


@dataclass(frozen=True)
class MarketLean:
    market: str  # "spread" | "total"
    state: str  # "lean" | "no_lean" | "no_data" | "no_line"
    side_label: str | None  # "Los Angeles Rams -6.5 · home favorite" / "UNDER 44.5" / None
    rate: float | None  # leaned side's rate when state=="lean"; else the reference rate
    n: int | None
    best_for_lean: BestLine | None  # price for the leaned side (state == "lean")
    best_primary: BestLine | None  # home / over — always shown for shopping
    best_secondary: BestLine | None  # away / under


def _teams(matchup: str) -> tuple[str, str]:
    """('Away at Home') -> (away, home)."""
    away, _, home = matchup.partition(" at ")
    return away, home


def _enough(n: int) -> bool:
    return n >= INSUFFICIENT_SAMPLE_THRESHOLD


def spread_lean(game: ThisWeekGame, spread_rates: RatesMap | None) -> MarketLean:
    cons = game.cons_spread_home
    home_best, away_best = game.best_spread_home, game.best_spread_away
    if cons is None:
        return MarketLean("spread", "no_line", None, None, None, None, home_best, away_best)
    bucket = bucket_spread(cons)
    ctx = (spread_rates or {}).get(bucket)
    if ctx is None or ctx.get("n", 0) == 0:
        return MarketLean("spread", "no_data", None, None, None, None, home_best, away_best)

    home_rate = ctx.get("win_rate", 0.0)
    away_rate = 1.0 - home_rate
    n = ctx.get("n", 0)
    away_team, home_team = _teams(game.matchup)
    is_pickem = bucket == "pickem"
    home_is_fav = cons < 0

    if _enough(n) and not is_pickem and home_rate >= BREAKEVEN_AT_NEG_110:
        kind = "home favorite" if home_is_fav else "home dog"
        label = f"{home_team} {cons:+g} · {kind}"
        return MarketLean("spread", "lean", label, home_rate, n, home_best, home_best, away_best)

    if _enough(n) and not is_pickem and away_rate >= BREAKEVEN_AT_NEG_110:
        kind = "away dog" if home_is_fav else "away favorite"
        label = f"{away_team} {-cons:+g} · {kind}"
        return MarketLean("spread", "lean", label, away_rate, n, away_best, home_best, away_best)

    return MarketLean("spread", "no_lean", None, home_rate, n, None, home_best, away_best)


def total_lean(game: ThisWeekGame, total_rates: RatesMap | None) -> MarketLean:
    cons = game.cons_total
    over_best, under_best = game.best_total_over, game.best_total_under
    if cons is None:
        return MarketLean("total", "no_line", None, None, None, None, over_best, under_best)
    bucket = bucket_total(cons)
    ctx = (total_rates or {}).get(bucket)
    if ctx is None or ctx.get("n", 0) == 0:
        return MarketLean("total", "no_data", None, None, None, None, over_best, under_best)

    over_rate = ctx.get("win_rate", 0.0)
    under_rate = 1.0 - over_rate
    n = ctx.get("n", 0)

    if _enough(n) and over_rate >= BREAKEVEN_AT_NEG_110:
        label = f"OVER {cons:g}"
        return MarketLean("total", "lean", label, over_rate, n, over_best, over_best, under_best)
    if _enough(n) and under_rate >= BREAKEVEN_AT_NEG_110:
        label = f"UNDER {cons:g}"
        return MarketLean("total", "lean", label, under_rate, n, under_best, over_best, under_best)

    return MarketLean("total", "no_lean", None, over_rate, n, None, over_best, under_best)


def game_leans(
    game: ThisWeekGame, spread_rates: RatesMap | None, total_rates: RatesMap | None
) -> tuple[MarketLean, MarketLean]:
    """The spread read and the total read for one game, in that order."""
    return spread_lean(game, spread_rates), total_lean(game, total_rates)
