import math

from scipy.stats import binomtest as _scipy_binomtest

from engine.stats_utils import (
    BREAKEVEN_AT_NEG_110,
    american_to_decimal,
    binomial_pvalue,
    decimal_to_american,
    kelly_fraction,
    roi,
    wilson_ci,
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
    import pytest

    with pytest.raises(ValueError):
        kelly_fraction(-0.1, 2.0)
    with pytest.raises(ValueError):
        kelly_fraction(1.1, 2.0)
