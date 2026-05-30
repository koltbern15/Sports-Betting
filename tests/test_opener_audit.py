"""Tests for engine.opener_audit — pure audit math on synthetic data."""

from __future__ import annotations

import math

import pytest

from engine.opener_audit import (
    agreement_rate,
    movement_stats,
    outliers,
)


def test_agreement_rate_within_tolerance():
    a = [-3.0, -7.0, 2.5, 0.0]
    b = [-3.0, -7.5, 2.5, 0.5]
    assert agreement_rate(a, b, tol=0.5) == pytest.approx(1.0)
    assert agreement_rate(a, b, tol=0.4) == pytest.approx(0.5)


def test_agreement_rate_skips_none_pairs():
    a = [-3.0, None, 2.0]
    b = [-3.0, 5.0, None]
    assert agreement_rate(a, b, tol=0.5) == pytest.approx(1.0)


def test_agreement_rate_no_comparable_pairs_is_nan():
    assert math.isnan(agreement_rate([None], [None], tol=0.5))


def test_movement_stats_close_minus_open():
    opens = [-3.0, -7.0]
    closes = [-3.5, -6.0]
    stats = movement_stats(opens, closes)
    assert stats["mean"] == pytest.approx(0.25)
    assert stats["n"] == 2


def test_outliers_flags_large_abs_diff():
    opens = [-3.0, -3.0, -3.0]
    closes = [-3.5, -10.0, -3.0]
    flagged = outliers(opens, closes, threshold=3.0)
    assert flagged == [1]
