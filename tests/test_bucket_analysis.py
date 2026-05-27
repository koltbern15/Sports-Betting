"""Smoke tests for the shared bucket-analysis helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.bucket_analysis import (
    DISCLAIMER,
    BucketMetrics,
    compute_metrics,
    format_table,
    write_csv,
)


def test_compute_metrics_basic_no_payouts():
    m = compute_metrics("x", wins=10, losses=8, pushes=2)
    assert m.bucket == "x"
    assert m.n == 20
    assert m.wins == 10
    assert m.losses == 8
    assert m.pushes == 2
    assert m.win_rate == 10 / 18
    assert m.push_rate == 2 / 20
    assert m.roi_neg110 != m.roi_neg105
    assert 0.0 <= m.ci_low <= m.ci_high <= 1.0


def test_compute_metrics_with_payouts_uses_dollar_weighted_roi():
    payouts = [1.30, -1.0, 1.30, -1.0]
    m = compute_metrics("x", wins=2, losses=2, pushes=0, payouts=payouts)
    assert m.roi_neg110 == pytest.approx(0.15)
    assert m.roi_neg105 == pytest.approx(0.15)
    # The two ROI columns are identical when payouts is supplied
    assert m.roi_neg110 == m.roi_neg105


def test_compute_metrics_insufficient_sample_threshold():
    below = compute_metrics("x", wins=20, losses=20, pushes=0)
    above = compute_metrics("x", wins=30, losses=20, pushes=0)
    assert below.insufficient_sample is True
    assert above.insufficient_sample is False


def test_format_table_renders_header_and_low_n_marker():
    rows = [
        compute_metrics("a", 30, 30, 0),
        compute_metrics("b", 5, 5, 0),
    ]
    out = format_table(rows)
    assert "bucket" in out and "ROI -110" in out
    assert "*" in out
    assert "a" in out and "b" in out


def test_write_csv_writes_disclaimer_then_rows(tmp_path: Path):
    rows = [compute_metrics("a", 10, 8, 2)]
    out = tmp_path / "out.csv"
    write_csv(rows, out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith(f"# {DISCLAIMER}")
    assert "bucket,n,wins" in text
    assert "a,20,10,8,2" in text


def test_bucket_metrics_dataclass_default_by_season_is_empty_dict():
    m = BucketMetrics(
        bucket="x", n=0, wins=0, losses=0, pushes=0,
        win_rate=0.0, push_rate=0.0,
        roi_neg110=0.0, roi_neg105=0.0,
        p_value=1.0, ci_low=0.0, ci_high=1.0,
        insufficient_sample=True,
    )
    assert m.by_season == {}
