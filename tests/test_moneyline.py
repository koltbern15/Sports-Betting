"""Tests for engine.moneyline."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.db import connect, init_schema
from engine.moneyline import (
    BUCKET_ORDER_ML,
    MoneylineReport,
    _payout_for_bet,
    bucket_ml,
    derive_ml_from_spread,
    moneyline_by_odds_bucket,
)
from ingestion.loader import load_csv_to_db


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


def test_derive_ml_steep_spread_price_floors_near_minus_10000():
    """Bug fix: at spreads steeper than ~-24 the proportional vig pushed implied
    prob above 1.0, producing -99,999,900. The price must now floor near -10000."""
    ml_home, ml_away = derive_ml_from_spread(-26.5)
    assert ml_home >= -10000, f"home price too extreme: {ml_home}"
    # A winning heavy-fav bet must pay a realistic (small but non-trivial) amount,
    # not ~0.000001 as the old -99,999,900 price produced.
    assert _payout_for_bet(ml_home, True) > 0.001

    # Mirror case: at +26.5 the AWAY side is the steep favorite and must also floor
    ml_home2, ml_away2 = derive_ml_from_spread(+26.5)
    assert ml_away2 >= -10000, f"away price too extreme: {ml_away2}"
    assert _payout_for_bet(ml_away2, True) > 0.001


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


def _build_db_from_fixture(tmp_path: Path, fixture: str) -> Path:
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    init_schema(conn)
    conn.close()
    load_csv_to_db(Path(fixture), db_path)
    return db_path


def test_moneyline_aggregator_returns_report_with_11_buckets(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/moneyline_20.csv")
    conn = connect(db)
    try:
        report = moneyline_by_odds_bucket(conn)
    finally:
        conn.close()
    assert isinstance(report, MoneylineReport)
    assert len(report.rows) == 11
    assert [r.bucket for r in report.rows] == BUCKET_ORDER_ML


def test_moneyline_aggregator_per_bucket_counts_match_fixture(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/moneyline_20.csv")
    conn = connect(db)
    try:
        report = moneyline_by_odds_bucket(conn)
    finally:
        conn.close()
    by = {r.bucket: r for r in report.rows}

    # Corrected expected counts (verified by running derive_ml_from_spread + bucket_ml
    # against the T8 fixture). The plan's original T9 table was off for mid_dog/big_dog.
    expected = {
        "ml_heavy_fav":  (9, 6, 3, 0),
        "ml_big_fav":    (0, 0, 0, 0),
        "ml_mid_fav":    (6, 4, 2, 0),
        "ml_small_fav":  (3, 2, 1, 0),
        "ml_slight_fav": (4, 2, 2, 0),
        "ml_pickem":     (0, 0, 0, 0),
        "ml_slight_dog": (3, 1, 2, 0),
        "ml_small_dog":  (3, 1, 2, 0),
        "ml_mid_dog":    (3, 1, 2, 0),
        "ml_big_dog":    (3, 1, 2, 0),
        "ml_heavy_dog":  (6, 2, 4, 0),
    }
    for bucket, (n, w, losses, p) in expected.items():
        m = by[bucket]
        assert (m.n, m.wins, m.losses, m.pushes) == (n, w, losses, p), bucket


def test_moneyline_aggregator_total_entries_is_40(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/moneyline_20.csv")
    conn = connect(db)
    try:
        report = moneyline_by_odds_bucket(conn)
    finally:
        conn.close()
    total_n = sum(r.n for r in report.rows)
    assert total_n == 40  # 20 games * 2 sides


def test_moneyline_payout_helper_loss_returns_minus_one():
    from engine.moneyline import _payout_for_bet
    assert _payout_for_bet(ml_price=-150, won=False) == -1.0


def test_moneyline_payout_helper_win_at_minus_110_pays_100_over_110():
    from engine.moneyline import _payout_for_bet
    assert _payout_for_bet(ml_price=-110, won=True) == pytest.approx(100.0 / 110.0)


def test_moneyline_payout_helper_win_at_plus_150_pays_1_50():
    from engine.moneyline import _payout_for_bet
    assert _payout_for_bet(ml_price=+150, won=True) == pytest.approx(1.50)


def test_moneyline_payout_helper_push_returns_zero():
    from engine.moneyline import _payout_for_bet
    assert _payout_for_bet(ml_price=-110, won=None) == 0.0
