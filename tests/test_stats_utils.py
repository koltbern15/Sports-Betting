import math

from engine.stats_utils import american_to_decimal, decimal_to_american


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
