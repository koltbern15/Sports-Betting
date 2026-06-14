import math

import pytest

from engine.ats import ats_by_spread_bucket, bucket_spread
from engine.bucket_analysis import BucketMetrics, compute_metrics
from engine.db import connect, init_schema
from ingestion.loader import load_csv_to_db


@pytest.mark.parametrize(
    "spread, expected",
    [
        (-20.0, "home_fav_14.5+"),
        (-14.5, "home_fav_14.5+"),
        (-14.0, "home_fav_10.5_14"),
        (-10.5, "home_fav_10.5_14"),
        (-10.0, "home_fav_7.5_10"),
        (-7.5, "home_fav_7.5_10"),
        (-7.0, "home_fav_3.5_7"),
        (-3.5, "home_fav_3.5_7"),
        (-3.0, "home_fav_1_3"),
        (-1.0, "home_fav_1_3"),
        (-0.6, "home_fav_1_3"),
        (-0.5, "pickem"),
        (0.0, "pickem"),
        (0.5, "pickem"),
        (0.6, "home_dog_1_3"),
        (1.0, "home_dog_1_3"),
        (3.0, "home_dog_1_3"),
        (3.5, "home_dog_3.5_7"),
        (7.0, "home_dog_3.5_7"),
        (7.5, "home_dog_7.5_10"),
        (10.0, "home_dog_7.5_10"),
        (10.5, "home_dog_10.5_14"),
        (14.0, "home_dog_10.5_14"),
        (14.5, "home_dog_14.5+"),
        (20.0, "home_dog_14.5+"),
    ],
)
def test_bucket_spread_known_values(spread, expected):
    assert bucket_spread(spread) == expected


def test_bucket_spread_none_returns_none():
    assert bucket_spread(None) is None


def test_metrics_basic_case():
    # 60 covers, 40 losses, 0 pushes → win_rate = 0.60
    m = compute_metrics(bucket="home_fav_3.5_7", wins=60, losses=40, pushes=0)
    assert isinstance(m, BucketMetrics)
    assert m.bucket == "home_fav_3.5_7"
    assert m.n == 100
    assert m.wins == 60
    assert m.losses == 40
    assert m.pushes == 0
    assert math.isclose(m.win_rate, 0.6)
    assert math.isclose(m.push_rate, 0.0)
    assert math.isclose(m.roi_neg110, (60 * 10 / 11 - 40) / 100, abs_tol=1e-12)
    assert m.insufficient_sample is False
    # P-value vs 0.5238: 60/100 → significant in the right direction → small p
    assert m.p_value < 0.10


def test_metrics_with_pushes():
    m = compute_metrics(bucket="pickem", wins=10, losses=10, pushes=5)
    assert m.n == 25
    # win_rate excludes pushes from denominator
    assert math.isclose(m.win_rate, 0.5)
    # push_rate uses total
    assert math.isclose(m.push_rate, 0.2)


def test_metrics_insufficient_sample_flag_below_50():
    m = compute_metrics(bucket="home_fav_14.5+", wins=20, losses=20, pushes=0)
    assert m.insufficient_sample is True
    m2 = compute_metrics(bucket="home_fav_14.5+", wins=30, losses=20, pushes=0)
    # 30+20 = 50, threshold is wins+losses < 50 → exactly 50 is NOT insufficient
    assert m2.insufficient_sample is False


def test_metrics_zero_data():
    m = compute_metrics(bucket="pickem", wins=0, losses=0, pushes=0)
    assert m.n == 0
    assert m.win_rate == 0.0
    assert m.push_rate == 0.0
    assert m.p_value == 1.0
    assert m.ci_low == 0.0
    assert m.ci_high == 1.0
    assert m.insufficient_sample is True


def test_ats_by_spread_bucket_end_to_end(tmp_db_path, fixtures_dir):
    load_csv_to_db(
        fixtures_dir / "games_20_ats.csv", tmp_db_path,
        season_min=2024, season_max=2024,
    )
    conn = connect(tmp_db_path)
    try:
        report = ats_by_spread_bucket(conn)
    finally:
        conn.close()

    by_bucket = {row.bucket: row for row in report.rows}

    # Populated buckets
    fav_3_5_7 = by_bucket["home_fav_3.5_7"]
    assert (fav_3_5_7.wins, fav_3_5_7.losses, fav_3_5_7.pushes) == (2, 1, 0)

    fav_1_3 = by_bucket["home_fav_1_3"]
    assert (fav_1_3.wins, fav_1_3.losses, fav_1_3.pushes) == (2, 0, 1)
    assert fav_1_3.n == 3

    pickem = by_bucket["pickem"]
    assert (pickem.wins, pickem.losses, pickem.pushes) == (1, 1, 0)

    dog_1_3 = by_bucket["home_dog_1_3"]
    assert (dog_1_3.wins, dog_1_3.losses, dog_1_3.pushes) == (2, 1, 0)

    dog_3_5_7 = by_bucket["home_dog_3.5_7"]
    assert (dog_3_5_7.wins, dog_3_5_7.losses, dog_3_5_7.pushes) == (1, 2, 0)

    dog_7_5_10 = by_bucket["home_dog_7.5_10"]
    assert (dog_7_5_10.wins, dog_7_5_10.losses, dog_7_5_10.pushes) == (3, 3, 0)

    # Empty buckets must still appear in the report (with n=0, insufficient flag)
    fav_14plus = by_bucket["home_fav_14.5+"]
    assert fav_14plus.n == 0
    assert fav_14plus.insufficient_sample is True

    # All 11 buckets must be present
    assert {row.bucket for row in report.rows} == set(BUCKET_ORDER_LOCAL)


# Local copy of expected bucket order — must match engine/ats.py BUCKET_ORDER
BUCKET_ORDER_LOCAL = [
    "home_fav_14.5+",
    "home_fav_10.5_14",
    "home_fav_7.5_10",
    "home_fav_3.5_7",
    "home_fav_1_3",
    "pickem",
    "home_dog_1_3",
    "home_dog_3.5_7",
    "home_dog_7.5_10",
    "home_dog_10.5_14",
    "home_dog_14.5+",
]


def test_ats_report_includes_by_season_for_populated_buckets(tmp_db_path, fixtures_dir):
    load_csv_to_db(
        fixtures_dir / "games_20_ats.csv", tmp_db_path,
        season_min=2024, season_max=2024,
    )
    conn = connect(tmp_db_path)
    try:
        report = ats_by_spread_bucket(conn)
    finally:
        conn.close()
    by_bucket = {row.bucket: row for row in report.rows}
    # Fixture is all 2024 → exactly one season key, win_rate matches the aggregate
    fav_1_3 = by_bucket["home_fav_1_3"]
    assert list(fav_1_3.by_season.keys()) == [2024]
    # decided = 2 (2 covers, 0 losses), pushes excluded from win_rate denom
    assert fav_1_3.by_season[2024] == 1.0


def test_ats_csv_output_is_written(fixtures_dir, tmp_path, monkeypatch):
    # Load fixture into the canonical DB path the CLI expects
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "nfl_betting.sqlite"
    load_csv_to_db(
        fixtures_dir / "games_20_ats.csv", db_path,
        season_min=2024, season_max=2024,
    )

    monkeypatch.chdir(tmp_path)
    out_csv = tmp_path / "data" / "processed" / "ats_by_bucket.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # Call the CLI in-process for speed (avoid subprocess overhead)
    from engine.ats import _main  # noqa: PLC0415 — internal test API

    rc = _main([])

    assert rc == 0
    assert out_csv.exists()
    content = out_csv.read_text(encoding="utf-8")
    # Disclaimer must be in the file
    assert "Gamble responsibly." in content
    # Header line must include the metrics columns
    assert "bucket" in content
    assert "roi_neg110" in content
    assert "p_value" in content


def test_ats_stdout_includes_disclaimer(capsys, fixtures_dir, tmp_path, monkeypatch):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    load_csv_to_db(
        fixtures_dir / "games_20_ats.csv", db_dir / "nfl_betting.sqlite",
        season_min=2024, season_max=2024,
    )
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "processed").mkdir(parents=True, exist_ok=True)

    from engine.ats import _main

    _main([])
    captured = capsys.readouterr()
    assert "Gamble responsibly." in captured.out
    assert "home_fav_3.5_7" in captured.out


def _seed_two_seasons(conn):
    init_schema(conn)
    conn.executemany(
        "INSERT INTO games(game_id,season,week,game_date,home_team,away_team,home_score,away_score)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [("g1", 2019, 1, "2019-09-08", "A", "B", 27, 17),
         ("g2", 2023, 1, "2023-09-10", "C", "D", 27, 17)],
    )
    conn.executemany(
        "INSERT INTO betting_lines"
        "(game_id,spread_home_close,total_close,home_spread_result,total_result)"
        " VALUES (?,?,?,?,?)",
        [("g1", -6.5, 44.5, "cover", "over"),
         ("g2", -6.5, 44.5, "cover", "over")],
    )
    conn.commit()


def test_ats_season_filter_narrows_sample(memory_db):
    _seed_two_seasons(memory_db)
    full = {r.bucket: r for r in ats_by_spread_bucket(memory_db).rows}
    assert full["home_fav_3.5_7"].n == 2
    narrow = {r.bucket: r for r in ats_by_spread_bucket(memory_db, (2019, 2019)).rows}
    assert narrow["home_fav_3.5_7"].n == 1
