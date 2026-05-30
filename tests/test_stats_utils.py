import math

import pytest
from scipy.stats import binomtest as _scipy_binomtest

from engine.stats_utils import (
    BREAKEVEN_AT_NEG_110,
    american_to_decimal,
    binomial_pvalue,
    decimal_to_american,
    kelly_fraction,
    mde_mean_at_power,
    mde_winrate_at_power,
    mean_needed_for_ci,
    roi,
    roi_from_win_prob,
    std_from_mean_ci,
    wilson_ci,
    winrate_needed_for_ci,
)


def test_american_to_decimal_negative():
    # -110 → 1 + 100/110 = 1.909090...
    assert math.isclose(american_to_decimal(-110), 1 + 100 / 110, rel_tol=0, abs_tol=1e-9)


def test_american_to_decimal_positive():
    # +150 → 1 + 150/100 = 2.50
    assert math.isclose(american_to_decimal(150), 2.50, abs_tol=1e-9)


def test_decimal_to_american_negative():
    # 1.909090... → -110
    assert decimal_to_american(1 + 100 / 110) == -110


def test_decimal_to_american_positive():
    # 2.50 → +150
    assert decimal_to_american(2.50) == 150


def test_roundtrip_negative():
    assert decimal_to_american(american_to_decimal(-110)) == -110


def test_roundtrip_positive():
    assert decimal_to_american(american_to_decimal(150)) == 150


def test_roi_break_even_at_neg110_using_round_numbers():
    # 55W/45L at -110: 55 * 10/11 = 50.0 exactly; net = +5; ROI = 5/100 = 0.05
    assert math.isclose(roi(55, 45, 0, -110), 0.05, abs_tol=1e-12)


def test_roi_losing_record_at_neg110():
    # 50W/50L at -110: 50*10/11 - 50 = -4.5454...; / 100 = -0.045454...
    assert math.isclose(roi(50, 50, 0, -110), -50 / 11 / 100, abs_tol=1e-12)


def test_roi_pushes_only_inflate_denominator():
    # 10W/10L/5P at -110: net PnL = 10*10/11 - 10 = -10/11; bets = 25
    assert math.isclose(roi(10, 10, 5, -110), -(10 / 11) / 25, abs_tol=1e-12)


def test_roi_plus_money():
    # 30W/70L at +150: net = 30*1.5 - 70 = -25; bets = 100; ROI = -0.25
    assert math.isclose(roi(30, 70, 0, 150), -0.25, abs_tol=1e-12)


def test_roi_zero_bets_returns_zero():
    assert roi(0, 0, 0, -110) == 0.0


def test_binomial_pvalue_matches_scipy_60_of_100():
    expected = _scipy_binomtest(60, 100, BREAKEVEN_AT_NEG_110, alternative="greater").pvalue
    assert math.isclose(binomial_pvalue(60, 100, BREAKEVEN_AT_NEG_110), expected, abs_tol=1e-12)


def test_binomial_pvalue_matches_scipy_low_winrate():
    # Win rate below breakeven → p-value > 0.5
    expected = _scipy_binomtest(48, 100, BREAKEVEN_AT_NEG_110, alternative="greater").pvalue
    assert math.isclose(binomial_pvalue(48, 100, BREAKEVEN_AT_NEG_110), expected, abs_tol=1e-12)


def test_binomial_pvalue_zero_n_is_one():
    # No data → cannot reject null → pvalue = 1.0
    assert binomial_pvalue(0, 0, 0.5238) == 1.0


def test_binomial_pvalue_default_breakeven_is_neg110():
    expected = _scipy_binomtest(60, 100, BREAKEVEN_AT_NEG_110, alternative="greater").pvalue
    assert math.isclose(binomial_pvalue(60, 100), expected, abs_tol=1e-12)


def test_wilson_ci_55_of_100():
    # Hand-calculated with z=1.96:
    #   center = (55 + 1.92) / (100 + 3.8416) = 56.9208 / 103.8416 ≈ 0.54815
    #   half = 1.96 * sqrt(100*0.55*0.45 + 3.8416/4) / 103.8416 ≈ 0.09571
    # CI ≈ (0.45244, 0.64386)
    lo, hi = wilson_ci(55, 100, alpha=0.05)
    assert math.isclose(lo, 0.45244, abs_tol=1e-4)
    assert math.isclose(hi, 0.64386, abs_tol=1e-4)


def test_wilson_ci_zero_n_returns_zero_one():
    lo, hi = wilson_ci(0, 0)
    assert (lo, hi) == (0.0, 1.0)


def test_wilson_ci_all_wins_does_not_exceed_one():
    lo, hi = wilson_ci(10, 10)
    assert 0.0 < lo < 1.0
    assert hi <= 1.0


def test_wilson_ci_all_losses_does_not_go_negative():
    lo, hi = wilson_ci(0, 10)
    assert lo >= 0.0
    assert 0.0 < hi < 1.0


def test_kelly_at_neg110_with_55pct_winprob():
    # f* = (0.55 * (10/11) - 0.45) / (10/11) = 0.055 exact
    assert math.isclose(kelly_fraction(0.55, 1 + 10 / 11), 0.055, abs_tol=1e-12)


def test_kelly_clamps_to_zero_when_negative_edge():
    # p=0.45 at -110 → negative EV; Kelly should clamp to 0 (no bet)
    assert kelly_fraction(0.45, 1 + 10 / 11) == 0.0


def test_kelly_at_plus_odds():
    # p=0.40 at +150 (decimal 2.5, b=1.5):
    # f* = (0.4*1.5 - 0.6) / 1.5 = 0.0 / 1.5 = 0.0 (exactly break-even, no bet)
    assert math.isclose(kelly_fraction(0.40, 2.5), 0.0, abs_tol=1e-12)


def test_kelly_at_plus_odds_positive_edge():
    # p=0.45 at +150 (b=1.5):
    # f* = (0.45*1.5 - 0.55) / 1.5 = 0.125 / 1.5 ≈ 0.0833...
    assert math.isclose(kelly_fraction(0.45, 2.5), 0.125 / 1.5, abs_tol=1e-12)


def test_kelly_invalid_prob_raises():
    with pytest.raises(ValueError):
        kelly_fraction(-0.1, 2.0)
    with pytest.raises(ValueError):
        kelly_fraction(1.1, 2.0)


# === dollar_weighted_roi ===

def test_dollar_weighted_roi_empty_returns_zero():
    from engine.stats_utils import dollar_weighted_roi
    assert dollar_weighted_roi([]) == 0.0


def test_dollar_weighted_roi_all_wins_at_fixed_price():
    from engine.stats_utils import dollar_weighted_roi
    assert dollar_weighted_roi([1.0, 1.0, 1.0, 1.0]) == 1.0


def test_dollar_weighted_roi_all_losses():
    from engine.stats_utils import dollar_weighted_roi
    assert dollar_weighted_roi([-1.0, -1.0, -1.0]) == -1.0


def test_dollar_weighted_roi_mixed_with_pushes():
    from engine.stats_utils import dollar_weighted_roi
    payouts = [0.909, -1.0, 0.0, 1.30]
    assert dollar_weighted_roi(payouts) == sum(payouts) / 4


# === bootstrap helpers ===

def test_bootstrap_mean_ci_brackets_known_mean():
    from engine.stats_utils import bootstrap_mean_ci
    pnls = [0.5, -0.3, 0.4, -0.2, 0.3, -0.1, 0.2, 0.0, 0.2, 0.0]
    lo, hi = bootstrap_mean_ci(pnls, seed=42)
    assert lo < hi
    # Sample mean = 0.10; CI should bracket it
    assert lo < 0.10 < hi


def test_bootstrap_mean_ci_all_positive():
    from engine.stats_utils import bootstrap_mean_ci
    pnls = [0.5, 0.4, 0.3, 0.6, 0.5, 0.4]
    lo, _hi = bootstrap_mean_ci(pnls, seed=42)
    assert lo > 0  # CI lower bound should be positive when all returns positive


def test_bootstrap_mean_ci_empty_raises():
    from engine.stats_utils import bootstrap_mean_ci
    with pytest.raises(ValueError, match="empty"):
        bootstrap_mean_ci([], seed=42)


def test_bootstrap_pvalue_mean_gt_zero_clear_positive():
    from engine.stats_utils import bootstrap_pvalue_mean_gt_zero
    pnls = [1.0] * 100
    p = bootstrap_pvalue_mean_gt_zero(pnls, seed=42)
    assert p < 0.01  # essentially zero — no bootstrap sample has mean <= 0


def test_bootstrap_pvalue_mean_gt_zero_clear_negative():
    from engine.stats_utils import bootstrap_pvalue_mean_gt_zero
    pnls = [-1.0] * 100
    p = bootstrap_pvalue_mean_gt_zero(pnls, seed=42)
    assert p > 0.99  # essentially one — every sample has mean <= 0


def test_bootstrap_pvalue_mean_gt_zero_seeded_deterministic():
    from engine.stats_utils import bootstrap_pvalue_mean_gt_zero
    pnls = [0.1, -0.1, 0.2, -0.05, 0.15, -0.08]
    p1 = bootstrap_pvalue_mean_gt_zero(pnls, seed=42)
    p2 = bootstrap_pvalue_mean_gt_zero(pnls, seed=42)
    assert p1 == p2  # deterministic given seed


# === roi_from_win_prob ===

def test_roi_from_win_prob_breakeven_is_zero():
    # 110/210 win rate at -110 is exactly breakeven → ROI 0
    assert roi_from_win_prob(110 / 210, -110) == pytest.approx(0.0, abs=1e-9)


def test_roi_from_win_prob_55_pct():
    # 0.55 * 0.909091 - 0.45 = 0.04999...
    assert roi_from_win_prob(0.55, -110) == pytest.approx(0.05, abs=1e-4)


def test_roi_from_win_prob_propagates_nan():
    assert math.isnan(roi_from_win_prob(float("nan")))


# === mde_winrate_at_power ===

def test_mde_winrate_at_power_n100():
    # At n=100 a static edge must be ~62.8% win rate (~+20% ROI) to be 80%-power
    # detectable vs the -110 breakeven. (Matches the audit's power table.)
    p1 = mde_winrate_at_power(100)
    assert 0.62 < p1 < 0.64
    assert roi_from_win_prob(p1) == pytest.approx(0.20, abs=0.02)


def test_mde_winrate_at_power_n500():
    p1 = mde_winrate_at_power(500)
    assert 0.565 < p1 < 0.575
    assert roi_from_win_prob(p1) == pytest.approx(0.084, abs=0.02)


def test_mde_winrate_at_power_shrinks_with_n():
    # More samples → smaller detectable edge
    assert mde_winrate_at_power(1000) < mde_winrate_at_power(100)


def test_mde_winrate_at_power_zero_n_is_nan():
    assert math.isnan(mde_winrate_at_power(0))


# === winrate_needed_for_ci ===

def test_winrate_needed_for_ci_is_boundary():
    # The returned win rate's Wilson lower bound clears breakeven, and one fewer
    # win does not. Tests the inversion is exact, not off-by-one.
    n = 500
    p0 = 110 / 210
    p_needed = winrate_needed_for_ci(n, p0)
    w = round(p_needed * n)
    lo_at, _ = wilson_ci(w, n)
    lo_below, _ = wilson_ci(w - 1, n)
    assert lo_at > p0
    assert lo_below <= p0


def test_winrate_needed_for_ci_zero_n_is_nan():
    assert math.isnan(winrate_needed_for_ci(0))


# === mde_mean_at_power ===

def test_mde_mean_at_power_closed_form():
    # (z_a + z_b) * std / sqrt(n) = (1.281552 + 0.841621) * 1.0 / 20 = 0.106159
    assert mde_mean_at_power(400, 1.0) == pytest.approx(0.106159, abs=1e-4)


def test_mde_mean_at_power_bad_input_is_nan():
    assert math.isnan(mde_mean_at_power(0, 1.0))
    assert math.isnan(mde_mean_at_power(400, float("nan")))
    assert math.isnan(mde_mean_at_power(400, float("inf")))
    assert math.isnan(mean_needed_for_ci(400, float("inf")))


# === mean_needed_for_ci ===

def test_mean_needed_for_ci_closed_form():
    # z_{0.975} * std / sqrt(n) = 1.959964 * 1.0 / 20 = 0.097998
    assert mean_needed_for_ci(400, 1.0) == pytest.approx(0.097998, abs=1e-4)


# === std_from_mean_ci ===

def test_std_from_mean_ci_roundtrips_mean_needed():
    # A symmetric 95% CI of half-width 0.097998 at n=400 implies std=1.0
    std = std_from_mean_ci(-0.097998, 0.097998, 400)
    assert std == pytest.approx(1.0, abs=1e-3)


def test_std_from_mean_ci_bad_input_is_nan():
    assert math.isnan(std_from_mean_ci(float("nan"), 0.1, 400))
    assert math.isnan(std_from_mean_ci(-0.1, 0.1, 0))


def test_std_from_mean_ci_inverted_interval_is_nan():
    # ci_low > ci_high is bad input → NaN, not a negative std
    assert math.isnan(std_from_mean_ci(0.2, 0.1, 100))
