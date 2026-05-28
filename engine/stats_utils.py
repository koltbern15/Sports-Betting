"""Pure statistics utilities for sports-betting analysis.

All functions in this module are deterministic and side-effect-free.
"""

from __future__ import annotations

import math

from scipy.stats import binomtest as _binomtest
from scipy.stats import norm as _norm

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


def wilson_ci(wins: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a proportion.

    Preferred over the normal approximation at small n and when p_hat is near 0 or 1.
    Returns (0.0, 1.0) when n == 0 (no information).
    """
    if n == 0:
        return (0.0, 1.0)
    if wins < 0 or wins > n:
        raise ValueError(f"wins={wins} must be in [0, n={n}]")
    z = _norm.ppf(1.0 - alpha / 2.0)
    p_hat = wins / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def dollar_weighted_roi(payouts: list[float]) -> float:
    """ROI per unit stake given a list of per-bet net profits.

    Each payout is the net PnL of one unit-staked bet:
      +N for a winning bet that pays N units profit (e.g. 0.909 at -110, 1.30 at +130)
      -1.0 for a losing bet
      0.0 for a push
    Returns 0.0 if `payouts` is empty.
    """
    if not payouts:
        return 0.0
    return sum(payouts) / len(payouts)


def kelly_fraction(p_win: float, decimal_odds: float) -> float:
    """Optimal Kelly bet fraction.

    f* = (p * b - q) / b, where b = decimal_odds - 1, q = 1 - p.
    Clamped to >= 0 (do not place negative-EV bets).
    """
    if not 0.0 <= p_win <= 1.0:
        raise ValueError(f"p_win={p_win} must be in [0, 1]")
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal_odds={decimal_odds} must be > 1")
    b = decimal_odds - 1.0
    q = 1.0 - p_win
    f_star = (p_win * b - q) / b
    return max(0.0, f_star)


def bootstrap_mean_ci(
    values: list[float],
    *,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap 95% CI for the mean of `values`. Returns (ci_low, ci_high).

    Uses naive percentile bootstrap with deterministic seeding. Defaults give
    2.5%/97.5% percentile bounds.
    """
    import random

    if not values:
        raise ValueError("bootstrap_mean_ci called with empty values list")
    rng = random.Random(seed)
    n = len(values)
    boots = [sum(rng.choices(values, k=n)) / n for _ in range(n_boot)]
    boots.sort()
    lo_idx = int(n_boot * (alpha / 2))
    hi_idx = int(n_boot * (1 - alpha / 2))
    return boots[lo_idx], boots[hi_idx]


def bootstrap_pvalue_mean_gt_zero(
    values: list[float],
    *,
    n_boot: int = 2000,
    seed: int = 42,
) -> float:
    """Bootstrap p-value for H0: mean(values) <= 0.

    Returns the share of bootstrap resamples whose mean is <= 0.
    p < 0.05 indicates >95% of resamples show a positive mean (i.e., evidence
    that the true mean is positive).
    """
    import random

    if not values:
        raise ValueError("bootstrap_pvalue_mean_gt_zero called with empty values list")
    rng = random.Random(seed)
    n = len(values)
    boots = [sum(rng.choices(values, k=n)) / n for _ in range(n_boot)]
    return sum(1 for b in boots if b <= 0) / n_boot
