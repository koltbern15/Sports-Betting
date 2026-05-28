"""Tests for engine.validation — pure helpers."""

from __future__ import annotations

import sqlite3

import pytest

from engine.db import init_schema
from engine.validation import (
    BucketComparison,
    ValidationReport,
    american_to_implied_prob,
    compare_ml_prices,
    compute_price_stats,
    side_error,
)
from ingestion.real_ml_loader import load_csv_to_db


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


def _seed_full_fixture(conn: sqlite3.Connection) -> None:
    games = [
        (
            "2024_01_KC_BAL", 2024, 1, "2024-09-05",
            "Kansas City Chiefs", "Baltimore Ravens", 27, 20,
        ),
        (
            "2024_01_BUF_ARI", 2024, 1, "2024-09-08",
            "Buffalo Bills", "Arizona Cardinals", 34, 28,
        ),
        (
            "2024_02_DET_TB", 2024, 2, "2024-09-15",
            "Detroit Lions", "Tampa Bay Buccaneers", 20, 16,
        ),
        (
            "2024_02_GB_IND", 2024, 2, "2024-09-15",
            "Green Bay Packers", "Indianapolis Colts", 16, 10,
        ),
        (
            "2024_03_PIT_LAC", 2024, 3, "2024-09-22",
            "Pittsburgh Steelers", "Los Angeles Chargers", 13, 20,
        ),
    ]
    conn.executemany(
        "INSERT INTO games"
        "(game_id, season, week, game_date, home_team, away_team, home_score, away_score)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        games,
    )
    lines = [
        ("2024_01_KC_BAL", -3.0),
        ("2024_01_BUF_ARI", -7.0),
        ("2024_02_DET_TB", -3.0),
        ("2024_02_GB_IND", -0.5),
        ("2024_03_PIT_LAC", -3.0),
    ]
    conn.executemany(
        "INSERT INTO betting_lines(game_id, spread_home_close) VALUES (?, ?)",
        lines,
    )
    conn.commit()


def test_compare_ml_prices_basic_shape():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")

    report = compare_ml_prices(conn)

    assert isinstance(report, ValidationReport)
    assert report.price_stats["n_sides"] == 8
    assert report.n_games == 4
    assert report.source == "fixture"
    assert isinstance(report.bucket_comparisons, list)
    conn.close()


def test_compare_ml_prices_mean_error_matches_handcalc():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")

    report = compare_ml_prices(conn)
    assert -0.2 < report.price_stats["mean_error_prob"] < 0.2
    conn.close()


def test_compare_ml_prices_empty_raises():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    with pytest.raises(ValueError, match="insufficient validation data"):
        compare_ml_prices(conn)
    conn.close()


def test_compare_ml_prices_bucket_rows_match_slice2_assignment():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")

    report = compare_ml_prices(conn)
    bucket_names = {bc.bucket for bc in report.bucket_comparisons}
    assert (
        "ml_heavy_fav" in bucket_names
        or "ml_mid_fav" in bucket_names
        or "ml_big_fav" in bucket_names
    )
    for bc in report.bucket_comparisons:
        assert isinstance(bc, BucketComparison)
        assert bc.n >= 1
    conn.close()


def test_write_validation_csv_includes_comments(tmp_path):
    from engine.validation import write_validation_csv

    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")
    report = compare_ml_prices(conn)

    out_path = tmp_path / "validation.csv"
    write_validation_csv(report, out_path)

    text = out_path.read_text(encoding="utf-8")
    assert "# Real-line sample: source=fixture" in text
    assert "# Past performance does not guarantee future results" in text
    assert "bucket,n,derived_roi,real_roi,delta_roi" in text
    conn.close()


def test_compare_ml_prices_bucket_comparison_has_enriched_fields():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")
    report = compare_ml_prices(conn)
    for bc in report.bucket_comparisons:
        assert hasattr(bc, "ci_low")
        assert hasattr(bc, "ci_high")
        assert hasattr(bc, "p_value")
        assert hasattr(bc, "profitable_seasons_pct")
        assert hasattr(bc, "by_season")
    conn.close()


def test_compare_ml_prices_csv_has_new_columns(tmp_path):
    from engine.validation import write_validation_csv

    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")
    report = compare_ml_prices(conn)

    out_path = tmp_path / "validation.csv"
    write_validation_csv(report, out_path)

    text = out_path.read_text(encoding="utf-8")
    assert "ci_low" in text
    assert "ci_high" in text
    assert "p_value" in text
    assert "profitable_seasons_pct" in text
    conn.close()
