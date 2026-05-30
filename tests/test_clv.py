"""Tests for engine.clv — pure CLV math, grading, bucketing."""

from __future__ import annotations

import math

from engine.clv import (
    aggregate_clv,
    clamp_ok_spread,
    clamp_ok_total,
    clv_bucket,
    clv_spread,
    clv_total,
    spread_bet_result,
    total_bet_result,
)


def test_clv_spread_positive_when_close_more_home_favored():
    assert clv_spread(-3.0, -5.0) == 2.0


def test_clv_spread_negative_when_line_moves_against_home():
    assert clv_spread(-3.0, -1.0) == -2.0


def test_clv_total_positive_when_close_moves_up():
    assert clv_total(45.0, 47.0) == 2.0


def test_clv_total_zero_on_no_move():
    assert clv_total(45.0, 45.0) == 0.0


def test_clamp_spread_band():
    assert clamp_ok_spread(-26.5) is True
    assert clamp_ok_spread(28.0) is True
    assert clamp_ok_spread(40.0) is False
    assert clamp_ok_spread(None) is False


def test_clamp_total_band():
    assert clamp_ok_total(25.0) is True
    assert clamp_ok_total(75.0) is True
    assert clamp_ok_total(541.0) is False
    assert clamp_ok_total(10.0) is False
    assert clamp_ok_total(None) is False


def test_spread_bet_result_home_cover_is_win():
    assert spread_bet_result(27, 20, -3.0) == "win"
    assert spread_bet_result(21, 20, -3.0) == "loss"
    assert spread_bet_result(23, 20, -3.0) == "push"
    assert spread_bet_result(None, 20, -3.0) is None


def test_total_bet_result_over_is_win():
    assert total_bet_result(30, 20, 45.0) == "win"
    assert total_bet_result(20, 20, 45.0) == "loss"
    assert total_bet_result(25, 20, 45.0) == "push"


def test_clv_bucket_edges():
    assert clv_bucket(-3.0) == "clv_le_neg2"
    assert clv_bucket(-2.0) == "clv_le_neg2"
    assert clv_bucket(-1.0) == "clv_neg2_neg05"
    assert clv_bucket(0.0) == "clv_pm05"
    assert clv_bucket(0.5) == "clv_pm05"
    assert clv_bucket(1.0) == "clv_05_2"
    assert clv_bucket(2.0) == "clv_05_2"
    assert clv_bucket(5.0) == "clv_gt_2"
    assert clv_bucket(float("nan")) is None


def _bet(market, clv, result, season):
    return {"market": market, "clv": clv, "result": result, "season": season}


def test_aggregate_groups_by_market_and_bucket():
    bets = [
        _bet("spread", 3.0, "win", 2015),
        _bet("spread", 3.0, "win", 2016),
        _bet("spread", 3.0, "loss", 2017),
        _bet("spread", -3.0, "loss", 2015),
        _bet("total", 1.0, "win", 2015),
    ]
    rows = aggregate_clv(bets)
    by_key = {(r.market, r.clv_bucket): r for r in rows}
    assert by_key[("spread", "clv_gt_2")].n == 3
    assert by_key[("spread", "clv_gt_2")].wins == 2
    assert by_key[("spread", "clv_gt_2")].mean_clv == 3.0
    assert by_key[("spread", "clv_le_neg2")].n == 1
    assert ("total", "clv_05_2") in by_key


def test_aggregate_win_rate_and_power_columns_present():
    bets = [_bet("spread", 1.0, "win" if i % 2 == 0 else "loss", 2015 + (i % 3)) for i in range(10)]
    rows = aggregate_clv(bets)
    r = next(r for r in rows if r.market == "spread")
    assert 0.0 <= r.win_rate <= 1.0
    assert isinstance(r.mde80, float)
    assert isinstance(r.breakeven_needed, float)
    assert math.isfinite(r.ci_low) and math.isfinite(r.ci_high)


def test_aggregate_pushes_excluded_from_winrate_denominator():
    bets = [
        _bet("spread", 1.0, "win", 2015),
        _bet("spread", 1.0, "loss", 2015),
        _bet("spread", 1.0, "push", 2015),
    ]
    rows = aggregate_clv(bets)
    r = rows[0]
    assert r.n == 3
    assert r.win_rate == 0.5


def test_aggregate_rows_sorted_market_then_bucket_order():
    bets = [
        _bet("spread", 3.0, "win", 2015),
        _bet("spread", -3.0, "win", 2015),
        _bet("total", 3.0, "win", 2015),
    ]
    rows = aggregate_clv(bets)
    spread_buckets = [r.clv_bucket for r in rows if r.market == "spread"]
    assert spread_buckets.index("clv_le_neg2") < spread_buckets.index("clv_gt_2")
