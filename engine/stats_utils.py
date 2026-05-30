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
    # Indices placed symmetrically so the interval is exactly (1-alpha) wide.
    # boots[lo_idx] is the lower-tail cutoff; boots[hi_idx] is the upper-tail
    # cutoff. Using `n_boot - 1 - lo_idx` for hi_idx makes the trimmed tails
    # exactly the same size on both ends.
    lo_idx = int(n_boot * (alpha / 2))
    hi_idx = n_boot - 1 - lo_idx
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


def roi_from_win_prob(p: float, american_odds: int = -110) -> float:
    """Expected ROI per 1-unit bet for a true win probability `p` at given odds.

    roi = p * profit_per_win - (1 - p). At -110, p = 110/210 returns 0.
    Propagates NaN (so callers can pass through unsolved power estimates).
    """
    if p != p:  # NaN
        return math.nan
    profit_per_win = american_to_decimal(american_odds) - 1.0
    return p * profit_per_win - (1.0 - p)


def mde_winrate_at_power(
    n: int,
    p0: float = BREAKEVEN_AT_NEG_110,
    *,
    alpha: float = 0.10,
    power: float = 0.80,
) -> float:
    """Smallest TRUE win rate p1 > p0 detectable at `power`, one-sided level `alpha`,
    given n decided bets. Normal approximation; solved numerically.

    Solves  n = (z_a*sqrt(p0*q0) + z_b*sqrt(p1*q1))**2 / (p1 - p0)**2  for p1.
    required_n(p1) is monotonically decreasing on (p0, 1): a larger true effect
    needs fewer samples. Returns NaN if n <= 0 or n is too small to detect any
    p1 < 1 (i.e. required_n at p1≈1 still exceeds n).
    """
    if n <= 0:
        return math.nan
    z_a = _norm.ppf(1.0 - alpha)
    z_b = _norm.ppf(power)

    def required_n(p1: float) -> float:
        se0 = math.sqrt(p0 * (1.0 - p0))
        se1 = math.sqrt(p1 * (1.0 - p1))
        return (z_a * se0 + z_b * se1) ** 2 / (p1 - p0) ** 2

    lo, hi = p0 + 1e-9, 1.0 - 1e-9
    if required_n(hi) > n:
        return math.nan
    # Invariant: required_n(lo) > n, required_n(hi) <= n. Bisect for the crossing.
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if required_n(mid) > n:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def winrate_needed_for_ci(
    n: int,
    p0: float = BREAKEVEN_AT_NEG_110,
    *,
    alpha: float = 0.05,
) -> float:
    """Smallest observed win rate whose Wilson (1-alpha) CI lower bound exceeds p0,
    given n decided bets. Wilson lower bound is monotone increasing in wins, so the
    first qualifying win count is the minimum. Returns NaN if n <= 0 or unattainable.
    """
    if n <= 0:
        return math.nan
    for w in range(0, n + 1):
        lo, _hi = wilson_ci(w, n, alpha)
        if lo > p0:
            return w / n
    return math.nan


def mde_mean_at_power(
    n: int,
    std: float,
    *,
    alpha: float = 0.10,
    power: float = 0.80,
) -> float:
    """Smallest TRUE mean (vs null 0) detectable at `power`, one-sided level `alpha`,
    for n observations with per-observation std `std`.  mde = (z_a + z_b)*std/sqrt(n).
    Returns NaN on n <= 0 or non-finite/negative std.
    """
    if n <= 0 or not math.isfinite(std) or std < 0:
        return math.nan
    z_a = _norm.ppf(1.0 - alpha)
    z_b = _norm.ppf(power)
    return (z_a + z_b) * std / math.sqrt(n)


def mean_needed_for_ci(
    n: int,
    std: float,
    *,
    alpha: float = 0.05,
) -> float:
    """Smallest observed mean whose normal-theory (1-alpha) CI lower bound exceeds 0,
    given n observations with per-observation std `std`.  needed = z*std/sqrt(n),
    z = norm.ppf(1 - alpha/2). Returns NaN on n <= 0 or non-finite/negative std.
    """
    if n <= 0 or not math.isfinite(std) or std < 0:
        return math.nan
    z = _norm.ppf(1.0 - alpha / 2.0)
    return z * std / math.sqrt(n)


def std_from_mean_ci(
    ci_low: float,
    ci_high: float,
    n: int,
    *,
    alpha: float = 0.05,
) -> float:
    """Reconstruct per-observation std from a (1-alpha) normal-theory mean CI.

    Inverse of  mean ± z*std/sqrt(n).  Used to recover std when only the CI is
    available (e.g. a bootstrap CI persisted in a CSV). Approximation: assumes the
    interval is symmetric and normal-theory. Returns NaN on bad input.
    """
    if n <= 0 or ci_low != ci_low or ci_high != ci_high:
        return math.nan
    half = (ci_high - ci_low) / 2.0
    if half < 0:
        return math.nan
    z = _norm.ppf(1.0 - alpha / 2.0)
    return half * math.sqrt(n) / z
