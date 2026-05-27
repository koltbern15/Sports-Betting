import pandas as pd

from engine.db import connect, fetch_df, init_schema


def test_init_schema_creates_three_tables(memory_db):
    init_schema(memory_db)
    tables = {
        row["name"]
        for row in memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert tables == {"games", "betting_lines", "team_divisions"}


def test_init_schema_is_idempotent(memory_db):
    init_schema(memory_db)
    init_schema(memory_db)  # should not raise
    tables = {
        row["name"]
        for row in memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert tables == {"games", "betting_lines", "team_divisions"}


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
