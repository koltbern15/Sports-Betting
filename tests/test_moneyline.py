"""Tests for engine.moneyline."""

from __future__ import annotations

import pytest

from engine.moneyline import BUCKET_ORDER_ML, bucket_ml, derive_ml_from_spread


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


@pytest.mark.parametrize("spread", [-26.5, -24.5, -22.5, 22.0, 25.0])
def test_derive_ml_from_spread_does_not_crash_on_extreme_spreads(spread):
    """Real Kaggle data has spreads as extreme as -26.5; the function must not raise."""
    result = derive_ml_from_spread(spread)
    assert result is not None
    ml_home, ml_away = result
    assert isinstance(ml_home, int) and isinstance(ml_away, int)


@pytest.mark.parametrize(
    "ml,expected",
    [
        (-400, "ml_heavy_fav"),
        (-300, "ml_heavy_fav"),      # boundary: <= -300 → heavy
        (-299, "ml_big_fav"),
        (-250, "ml_big_fav"),
        (-249, "ml_mid_fav"),
        (-180, "ml_mid_fav"),
        (-179, "ml_small_fav"),
        (-130, "ml_small_fav"),
        (-129, "ml_slight_fav"),
        (-110, "ml_slight_fav"),
        (-109, "ml_pickem"),
        (+100, "ml_pickem"),
        (+109, "ml_pickem"),
        (+110, "ml_slight_dog"),
        (+129, "ml_slight_dog"),
        (+130, "ml_small_dog"),
        (+179, "ml_small_dog"),
        (+180, "ml_mid_dog"),
        (+249, "ml_mid_dog"),
        (+250, "ml_big_dog"),
        (+299, "ml_big_dog"),
        (+300, "ml_heavy_dog"),
        (+500, "ml_heavy_dog"),
    ],
)
def test_bucket_ml_classification(ml, expected):
    assert bucket_ml(ml) == expected


def test_bucket_ml_none_returns_none():
    assert bucket_ml(None) is None


def test_bucket_order_ml_has_11_unique_buckets():
    assert len(BUCKET_ORDER_ML) == 11
    assert len(set(BUCKET_ORDER_ML)) == 11
