"""Tests for engine.moneyline."""

from __future__ import annotations

import pytest

from engine.moneyline import derive_ml_from_spread


@pytest.mark.parametrize(
    "spread,expected_home,expected_away",
    [
        ( 0.0, -110, -110),
        (-3.0, -159, +130),
        (-7.0, -265, +211),
        (-14.0, -762, +511),
        ( 3.0, +130, -159),
    ],
)
def test_derive_ml_from_spread_reference_values(spread, expected_home, expected_away):
    ml_home, ml_away = derive_ml_from_spread(spread)
    assert abs(ml_home - expected_home) <= 2, f"home: expected {expected_home}, got {ml_home}"
    assert abs(ml_away - expected_away) <= 2, f"away: expected {expected_away}, got {ml_away}"


def test_derive_ml_from_spread_none_returns_none():
    assert derive_ml_from_spread(None) is None


def test_derive_ml_from_spread_symmetric_around_zero():
    # ML for spread -X should mirror ML for spread +X (home/away swap)
    a_home, a_away = derive_ml_from_spread(-5.0)
    b_home, b_away = derive_ml_from_spread(+5.0)
    assert a_home == b_away
    assert a_away == b_home


def test_derive_ml_from_spread_nan_returns_none():
    assert derive_ml_from_spread(float("nan")) is None
