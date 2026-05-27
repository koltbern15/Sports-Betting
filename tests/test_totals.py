"""Tests for engine.totals."""

from __future__ import annotations

import pytest

from engine.totals import BUCKET_ORDER_TOTALS, bucket_total


@pytest.mark.parametrize(
    "total,expected",
    [
        (35.0, "total_le_39_5"),
        (39.5, "total_le_39_5"),       # boundary inclusive on upper end
        (40.0, "total_40_42_5"),
        (42.5, "total_40_42_5"),
        (43.0, "total_43_45_5"),
        (45.5, "total_43_45_5"),
        (46.0, "total_46_48_5"),
        (48.5, "total_46_48_5"),
        (49.0, "total_49_51_5"),
        (51.5, "total_49_51_5"),
        (52.0, "total_ge_52"),
        (60.0, "total_ge_52"),
    ],
)
def test_bucket_total_classification(total, expected):
    assert bucket_total(total) == expected


def test_bucket_total_none_returns_none():
    assert bucket_total(None) is None


def test_bucket_order_totals_has_6_unique_buckets():
    assert len(BUCKET_ORDER_TOTALS) == 6
    assert len(set(BUCKET_ORDER_TOTALS)) == 6
