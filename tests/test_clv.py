"""Tests for engine.clv — pure CLV math, grading, bucketing."""

from __future__ import annotations

import math

from engine.clv import (
    ClvRow,
    aggregate_clv,
    build_bets_from_db,
    clamp_ok_spread,
    clamp_ok_total,
    clv_bucket,
    clv_spread,
    clv_total,
    spread_bet_result,
    total_bet_result,
    write_clv_csv,
)
from engine.db import connect, init_schema


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


def _seed(conn, game_id, season, hs, as_, src, open_sp, open_tot, close_sp, close_tot):
    conn.execute(
        "INSERT OR IGNORE INTO games"
        " (game_id, season, week, game_date, home_team, away_team, home_score, away_score)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (game_id, season, 1, f"{season}-09-13", "Home Team X", "Away Team Y", hs, as_),
    )
    conn.execute(
        "INSERT OR IGNORE INTO betting_lines"
        " (game_id, spread_home_close, total_close) VALUES (?,?,?)",
        (game_id, close_sp, close_tot),
    )
    conn.execute(
        "INSERT INTO opening_lines"
        " (game_id, source, open_spread_home, open_total) VALUES (?,?,?,?)",
        (game_id, src, open_sp, open_tot),
    )


def test_build_bets_from_db_uses_canonical_source_and_clamp():
    conn = connect(":memory:")
    init_schema(conn)
    _seed(conn, "g1", 2018, 27, 20, "aus", -3.0, 45.0, -5.0, 47.0)
    _seed(conn, "g1", 2018, 27, 20, "sbr", -10.0, 99.0, -5.0, 47.0)
    bets = build_bets_from_db(conn)
    spread_bets = [b for b in bets if b["market"] == "spread"]
    total_bets = [b for b in bets if b["market"] == "total"]
    assert len(spread_bets) == 1
    assert spread_bets[0]["clv"] == 2.0
    assert spread_bets[0]["result"] == "win"
    assert total_bets[0]["clv"] == 2.0
    conn.close()


def test_build_bets_skips_bad_opener_total_only_for_that_market():
    conn = connect(":memory:")
    init_schema(conn)
    _seed(conn, "g1", 2018, 27, 20, "aus", -3.0, 541.0, -5.0, 47.0)
    bets = build_bets_from_db(conn)
    assert any(b["market"] == "spread" for b in bets)
    assert not any(b["market"] == "total" for b in bets)
    conn.close()


def test_write_clv_csv_has_header_and_disclaimer(tmp_path):
    rows = [
        ClvRow("spread", "clv_gt_2", 100, 55, 3.2, 0.55, 0.05, 0.01, 0.10, 0.03, 0.6, 0.2, 0.18)
    ]
    out = tmp_path / "clv_report.csv"
    write_clv_csv(rows, out)
    text = out.read_text(encoding="utf-8")
    header = (
        "market,clv_bucket,n,mean_clv,win_rate,roi,ci_low,ci_high,"
        "p_value,profitable_seasons_pct,mde80,breakeven_needed"
    )
    assert header in text
    assert "# CLV report" in text
    assert "signal test" in text.lower()
    assert "spread,clv_gt_2,100" in text


def test_grade_at_close_regrades_at_closing_line():
    conn = connect(":memory:")
    init_schema(conn)
    # Home wins by 4. Opener -3 (covers), closer -6 (does NOT cover).
    _seed(conn, "g1", 2018, 24, 20, "aus", -3.0, 45.0, -6.0, 45.0)
    open_bets = build_bets_from_db(conn, grade_at="open")
    close_bets = build_bets_from_db(conn, grade_at="close")
    sp_open = next(b for b in open_bets if b["market"] == "spread")
    sp_close = next(b for b in close_bets if b["market"] == "spread")
    assert sp_open["result"] == "win"    # covered the -3 opener
    assert sp_close["result"] == "loss"  # did not cover the -6 closer
    assert sp_open["clv"] == sp_close["clv"] == 3.0  # open(-3) - close(-6)
    conn.close()


def test_grade_at_defaults_to_open():
    conn = connect(":memory:")
    init_schema(conn)
    _seed(conn, "g1", 2018, 24, 20, "aus", -3.0, 45.0, -6.0, 45.0)
    assert build_bets_from_db(conn) == build_bets_from_db(conn, grade_at="open")
    conn.close()
