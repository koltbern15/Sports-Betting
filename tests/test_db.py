import pandas as pd
import pytest

from engine.db import connect, fetch_df, init_schema


def test_init_schema_creates_all_tables(memory_db):
    init_schema(memory_db)
    tables = {
        row["name"]
        for row in memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert tables == {"games", "betting_lines", "team_divisions", "real_ml_lines", "opening_lines"}


def test_init_schema_is_idempotent(memory_db):
    init_schema(memory_db)
    init_schema(memory_db)  # should not raise
    tables = {
        row["name"]
        for row in memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert tables == {"games", "betting_lines", "team_divisions", "real_ml_lines", "opening_lines"}


def test_init_schema_seeds_team_divisions(memory_db):
    init_schema(memory_db)
    n = memory_db.execute("SELECT COUNT(*) AS c FROM team_divisions").fetchone()["c"]
    assert n == 32


def test_init_schema_enables_foreign_keys(memory_db):
    init_schema(memory_db)
    fk_on = memory_db.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_on == 1


def test_connect_to_file_creates_db(tmp_db_path):
    conn = connect(tmp_db_path)
    try:
        init_schema(conn)
        assert tmp_db_path.exists()
    finally:
        conn.close()


def test_fetch_df_returns_dataframe(memory_db):
    init_schema(memory_db)
    df = fetch_df(memory_db, "SELECT * FROM team_divisions")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 32
    assert {"team", "conference", "division"} <= set(df.columns)


def test_fetch_df_with_params(memory_db):
    init_schema(memory_db)
    df = fetch_df(memory_db, "SELECT * FROM team_divisions WHERE conference = ?", ("AFC",))
    assert len(df) == 16


def test_init_schema_creates_real_ml_lines_table():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='real_ml_lines'"
    )
    assert cursor.fetchone() is not None
    cursor = conn.execute("PRAGMA table_info(real_ml_lines)")
    cols = {row[1] for row in cursor.fetchall()}
    expected = {"game_id", "ml_home_real", "ml_away_real", "source", "source_url", "collected_at"}
    assert expected.issubset(cols), f"missing cols: {expected - cols}"
    conn.close()


def test_init_schema_real_ml_lines_idempotent():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    init_schema(conn)  # second call must not raise
    cursor = conn.execute("SELECT COUNT(*) FROM real_ml_lines")
    assert cursor.fetchone()[0] == 0
    conn.close()


def test_init_schema_creates_opening_lines_table():
    conn = connect(":memory:")
    init_schema(conn)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='opening_lines'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_opening_lines_composite_key_allows_two_sources_one_game():
    conn = connect(":memory:")
    init_schema(conn)
    conn.execute(
        "INSERT INTO games (game_id, season, week, game_date, home_team, away_team)"
        " VALUES ('g1', 2015, 1, '2015-09-13', 'Dallas Cowboys', 'New York Giants')"
    )
    conn.execute(
        "INSERT INTO opening_lines (game_id, source, open_spread_home, open_total)"
        " VALUES ('g1','sbr',-3.0,47.0)"
    )
    conn.execute(
        "INSERT INTO opening_lines (game_id, source, open_spread_home, open_total)"
        " VALUES ('g1','aus',-3.5,47.5)"
    )
    n = conn.execute("SELECT COUNT(*) FROM opening_lines WHERE game_id='g1'").fetchone()[0]
    assert n == 2
    conn.close()


def test_opening_lines_rejects_bad_source():
    import sqlite3
    conn = connect(":memory:")
    init_schema(conn)
    conn.execute(
        "INSERT INTO games (game_id, season, week, game_date, home_team, away_team)"
        " VALUES ('g1', 2015, 1, '2015-09-13', 'Dallas Cowboys', 'New York Giants')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO opening_lines (game_id, source, open_spread_home)"
            " VALUES ('g1','espn',-3.0)"
        )
    conn.close()
