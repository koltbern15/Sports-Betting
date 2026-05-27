import pytest

from engine.db import connect
from ingestion.loader import LoadReport, load_csv_to_db


@pytest.fixture
def loaded_db(tmp_db_path, fixtures_dir):
    load_csv_to_db(
        csv_path=fixtures_dir / "games_5.csv",
        db_path=tmp_db_path,
        season_min=2023,  # widen to include the wildcard game (season 2023, played Jan 2024)
        season_max=2024,
    )
    conn = connect(tmp_db_path)
    try:
        yield conn
    finally:
        conn.close()


def test_load_report_counts(tmp_db_path, fixtures_dir):
    report = load_csv_to_db(
        csv_path=fixtures_dir / "games_5.csv",
        db_path=tmp_db_path,
        season_min=2023,
        season_max=2024,
    )
    assert isinstance(report, LoadReport)
    assert report.rows_read == 5
    assert report.rows_inserted == 5


def test_load_creates_all_5_games(loaded_db):
    n = loaded_db.execute("SELECT COUNT(*) AS c FROM games").fetchone()["c"]
    assert n == 5


def test_load_creates_all_5_lines(loaded_db):
    n = loaded_db.execute("SELECT COUNT(*) AS c FROM betting_lines").fetchone()["c"]
    assert n == 5


def test_row1_chiefs_saints(loaded_db):
    g = loaded_db.execute(
        "SELECT g.*, b.spread_home_close, b.total_close, b.home_spread_result, b.total_result "
        "FROM games g JOIN betting_lines b ON b.game_id = g.game_id "
        "WHERE g.home_team = 'Kansas City Chiefs' AND g.season = 2024"
    ).fetchone()
    assert g["away_team"] == "New Orleans Saints"
    assert g["division_game_flag"] == 0
    assert g["primetime_flag"] == 1  # Monday
    assert g["playoff_flag"] == 0
    assert g["dome_flag"] == 0  # Arrowhead
    assert g["spread_home_close"] == -6.0
    assert g["total_close"] == 46.0
    assert g["home_spread_result"] == "cover"
    assert g["total_result"] == "under"


def test_row2_division_game_home_underdog(loaded_db):
    g = loaded_db.execute(
        "SELECT g.*, b.spread_home_close, b.home_spread_result, b.total_result "
        "FROM games g JOIN betting_lines b ON b.game_id = g.game_id "
        "WHERE g.home_team = 'Green Bay Packers' AND g.season = 2024"
    ).fetchone()
    assert g["division_game_flag"] == 1
    assert g["spread_home_close"] == 3.0
    assert g["home_spread_result"] == "cover"  # 25-27 margin -2 + 3 = +1
    assert g["total_result"] == "over"  # combined 52 > 40


def test_row3_pickem_with_missing_weather(loaded_db):
    g = loaded_db.execute(
        "SELECT g.*, b.spread_home_close, b.home_spread_result "
        "FROM games g JOIN betting_lines b ON b.game_id = g.game_id "
        "WHERE g.home_team = 'Houston Texans' AND g.season = 2024 AND g.week = 2"
    ).fetchone()
    assert g["spread_home_close"] == 0.0
    assert g["home_spread_result"] == "cover"  # home outright winner in pick'em
    assert g["dome_flag"] == 1  # NRG Stadium
    assert g["weather_temp"] is None
    assert g["weather_wind"] is None


def test_row4_playoff_week_encoded_as_100(loaded_db):
    g = loaded_db.execute(
        "SELECT * FROM games WHERE home_team = 'Buffalo Bills' AND season = 2023"
    ).fetchone()
    assert g["week"] == 100
    assert g["playoff_flag"] == 1
    assert g["primetime_flag"] == 0  # playoff override


def test_row5_missing_total_handled(loaded_db):
    g = loaded_db.execute(
        "SELECT b.total_close, b.total_result, b.home_spread_result "
        "FROM games g JOIN betting_lines b ON b.game_id = g.game_id "
        "WHERE g.home_team = 'Atlanta Falcons' AND g.season = 2024 AND g.week = 1"
    ).fetchone()
    assert g["total_close"] is None
    assert g["total_result"] is None
    assert g["home_spread_result"] == "loss"  # ATS still derivable from spread + scores


def test_load_is_idempotent(tmp_db_path, fixtures_dir):
    load_csv_to_db(fixtures_dir / "games_5.csv", tmp_db_path, season_min=2023, season_max=2024)
    load_csv_to_db(fixtures_dir / "games_5.csv", tmp_db_path, season_min=2023, season_max=2024)
    conn = connect(tmp_db_path)
    try:
        n_games = conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()["c"]
        n_lines = conn.execute("SELECT COUNT(*) AS c FROM betting_lines").fetchone()["c"]
        assert n_games == 5
        # betting_lines uses DELETE then INSERT keyed on (game_id) — also exactly 5
        assert n_lines == 5
    finally:
        conn.close()


def test_load_respects_season_filter(tmp_db_path, fixtures_dir):
    # season_min=2024 should drop the wildcard row (which is season 2023).
    report = load_csv_to_db(
        fixtures_dir / "games_5.csv", tmp_db_path, season_min=2024, season_max=2024
    )
    assert report.rows_inserted == 4
