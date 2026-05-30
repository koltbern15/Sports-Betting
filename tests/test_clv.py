"""Tests for engine.clv — pure CLV math, grading, bucketing."""

from __future__ import annotations

from engine.clv import (
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
