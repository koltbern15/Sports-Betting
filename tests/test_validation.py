"""Tests for engine.validation — pure helpers."""

from __future__ import annotations

import pytest

from engine.validation import (
    american_to_implied_prob,
    compute_price_stats,
    side_error,
)


def test_american_to_implied_prob_negative():
    # -200 -> 200 / (200 + 100) = 0.6667
    assert american_to_implied_prob(-200) == pytest.approx(0.6667, abs=1e-4)


def test_american_to_implied_prob_positive():
    # +150 -> 100 / (150 + 100) = 0.4
    assert american_to_implied_prob(150) == pytest.approx(0.4, abs=1e-6)


def test_american_to_implied_prob_neg110():
    assert american_to_implied_prob(-110) == pytest.approx(110 / 210, abs=1e-6)


def test_side_error_basic():
    err = side_error(real_ml=-150, derived_ml=-200)
    # real implied = 0.6, derived implied = 0.6667; error_prob = -0.0667
    assert err["error_prob"] == pytest.approx(0.6 - 2 / 3, abs=1e-4)
    assert err["error_ml"] == 50  # real (-150) - derived (-200) = +50


def test_compute_price_stats_basic():
    # 4 sides — derived consistently overstates favorite-side prob by +0.05
    sides = [
        {"real_ml": -150, "derived_ml": -200, "is_favorite": True},
        {"real_ml": -140, "derived_ml": -190, "is_favorite": True},
        {"real_ml": +130, "derived_ml": +170, "is_favorite": False},
        {"real_ml": +120, "derived_ml": +160, "is_favorite": False},
    ]
    stats = compute_price_stats(sides)
    assert stats["n_sides"] == 4
    # derived implied prob > real implied prob on fav side => negative mean_error_prob
    assert stats["mean_error_prob"] < 0
    assert stats["pct_sign_flip"] == 0.0
    assert stats["derived_overshades_favorites"] is True


def test_compute_price_stats_sign_flip():
    sides = [
        # real says dog, derived says fav — sign flip
        {"real_ml": +120, "derived_ml": -120, "is_favorite": False},
    ]
    stats = compute_price_stats(sides)
    assert stats["pct_sign_flip"] == 1.0


def test_compute_price_stats_no_data():
    with pytest.raises(ValueError, match="empty"):
        compute_price_stats([])
