"""Pure statistics utilities for sports-betting analysis.

All functions in this module are deterministic and side-effect-free.
"""

from __future__ import annotations

from scipy.stats import binomtest as _binomtest

BREAKEVEN_AT_NEG_110: float = 110 / 210  # ≈ 0.5238095…
BREAKEVEN_AT_NEG_105: float = 105 / 205  # ≈ 0.5121951…


def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal odds.

    Negative odds: pays 100/|odds| per unit risked.
    Positive odds: pays odds/100 per unit risked.
    """
    if odds == 0:
        raise ValueError("American odds of 0 are undefined")
    if odds < 0:
        return 1.0 + 100.0 / abs(odds)
    return 1.0 + odds / 100.0


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds back to American odds (rounded to nearest integer)."""
    if decimal_odds <= 1.0:
        raise ValueError("Decimal odds must be > 1.0")
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1.0) * 100)
    return -round(100.0 / (decimal_odds - 1.0))


def roi(wins: int, losses: int, pushes: int = 0, american_odds: int = -110) -> float:
    """Flat-unit ROI assuming 1 unit risked per bet.

    Pushes return stake (0 PnL) but still count in the denominator
    because the bettor tied up 1 unit on each.
    """
    total = wins + losses + pushes
    if total == 0:
        return 0.0
    profit_per_win = american_to_decimal(american_odds) - 1.0
    pnl = wins * profit_per_win - losses
    return pnl / total


def binomial_pvalue(wins: int, n: int, breakeven: float = BREAKEVEN_AT_NEG_110) -> float:
    """One-sided exact binomial test: P(X >= wins | n, breakeven).

    Asks: "Is this observed win rate significantly better than chance against the
    breakeven required to profit at the given juice?"
    Returns 1.0 when n == 0.
    """
    if n == 0:
        return 1.0
    if wins < 0 or wins > n:
        raise ValueError(f"wins={wins} must be in [0, n={n}]")
    return _binomtest(wins, n, breakeven, alternative="greater").pvalue
