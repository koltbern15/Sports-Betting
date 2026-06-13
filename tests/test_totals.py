"""Tests for engine.totals."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.db import connect, init_schema
from engine.totals import (
    BUCKET_ORDER_TOTALS,
    TotalsReport,
    bucket_total,
    totals_by_line_bucket,
)
from ingestion.loader import load_csv_to_db


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


def _build_db_from_fixture(tmp_path: Path, fixture: str) -> Path:
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    init_schema(conn)
    conn.close()
    load_csv_to_db(Path(fixture), db_path)
    return db_path


def test_totals_aggregator_returns_report_with_6_buckets(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/totals_20.csv")
    conn = connect(db)
    try:
        report = totals_by_line_bucket(conn)
    finally:
        conn.close()
    assert isinstance(report, TotalsReport)
    assert len(report.rows) == 6
    assert [r.bucket for r in report.rows] == BUCKET_ORDER_TOTALS


def test_totals_aggregator_per_bucket_counts_match_fixture(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/totals_20.csv")
    conn = connect(db)
    try:
        report = totals_by_line_bucket(conn)
    finally:
        conn.close()
    by = {r.bucket: r for r in report.rows}

    expected = {
        "total_le_39_5":  (2, 1, 1, 0),  # n, wins(over), losses(under), pushes
        "total_40_42_5":  (3, 2, 1, 0),
        "total_43_45_5":  (4, 3, 1, 0),
        "total_46_48_5":  (4, 2, 1, 1),
        "total_49_51_5":  (4, 2, 2, 0),
        "total_ge_52":    (3, 1, 1, 1),
    }
    for bucket, (n, w, losses, p) in expected.items():
        m = by[bucket]
        assert (m.n, m.wins, m.losses, m.pushes) == (n, w, losses, p), bucket


def test_totals_aggregator_total_counts_sum_to_20(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/totals_20.csv")
    conn = connect(db)
    try:
        report = totals_by_line_bucket(conn)
    finally:
        conn.close()
    total_n = sum(r.n for r in report.rows)
    assert total_n == 20


def test_totals_season_filter_narrows_sample(memory_db):
    init_schema(memory_db)
    memory_db.executemany(
        "INSERT INTO games(game_id,season,week,game_date,home_team,away_team,home_score,away_score)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [("g1", 2019, 1, "2019-09-08", "A", "B", 30, 20),
         ("g2", 2023, 1, "2023-09-10", "C", "D", 30, 20)],
    )
    memory_db.executemany(
        "INSERT INTO betting_lines"
        "(game_id,spread_home_close,total_close,home_spread_result,total_result)"
        " VALUES (?,?,?,?,?)",
        [("g1", -6.5, 44.5, "cover", "over"),
         ("g2", -6.5, 44.5, "cover", "over")],
    )
    memory_db.commit()
    full = {r.bucket: r for r in totals_by_line_bucket(memory_db).rows}
    assert full["total_43_45_5"].n == 2
    narrow = {r.bucket: r for r in totals_by_line_bucket(memory_db, (2019, 2019)).rows}
    assert narrow["total_43_45_5"].n == 1
