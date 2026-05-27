import math

from engine.stats_utils import american_to_decimal, decimal_to_american, roi


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
