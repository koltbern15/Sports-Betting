"""SQLite connection + schema management for the betting analytics DB."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from ingestion.divisions import DIVISIONS

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    game_id            TEXT PRIMARY KEY,
    season             INTEGER NOT NULL,
    week               INTEGER NOT NULL,
    game_date          TEXT NOT NULL,
    home_team          TEXT NOT NULL,
    away_team          TEXT NOT NULL,
    home_score         INTEGER,
    away_score         INTEGER,
    stadium            TEXT,
    dome_flag          INTEGER NOT NULL DEFAULT 0,
    weather_temp       INTEGER,
    weather_wind       INTEGER,
    weather_humidity   INTEGER,
    primetime_flag     INTEGER NOT NULL DEFAULT 0,
    playoff_flag       INTEGER NOT NULL DEFAULT 0,
    division_game_flag INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_games_season_week ON games(season, week);
CREATE INDEX IF NOT EXISTS idx_games_home_team   ON games(home_team);
CREATE INDEX IF NOT EXISTS idx_games_away_team   ON games(away_team);

CREATE TABLE IF NOT EXISTS betting_lines (
    line_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id            TEXT NOT NULL REFERENCES games(game_id),
    spread_home_close  REAL,
    total_close        REAL,
    home_spread_result TEXT
        CHECK (home_spread_result IN ('cover','push','loss')
            OR home_spread_result IS NULL),
    total_result       TEXT
        CHECK (total_result IN ('over','push','under') OR total_result IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_betting_lines_game ON betting_lines(game_id);

CREATE TABLE IF NOT EXISTS team_divisions (
    team       TEXT PRIMARY KEY,
    conference TEXT NOT NULL,
    division   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS real_ml_lines (
    game_id       TEXT PRIMARY KEY REFERENCES games(game_id),
    ml_home_real  INTEGER,
    ml_away_real  INTEGER,
    source        TEXT,
    source_url    TEXT,
    collected_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_real_ml_lines_game ON real_ml_lines(game_id);

CREATE TABLE IF NOT EXISTS opening_lines (
    game_id          TEXT NOT NULL REFERENCES games(game_id),
    source           TEXT NOT NULL CHECK (source IN ('sbr','aus')),
    open_spread_home REAL,
    open_total       REAL,
    open_ml_home     INTEGER,
    open_ml_away     INTEGER,
    source_url       TEXT,
    collected_at     TEXT,
    PRIMARY KEY (game_id, source)
);

CREATE INDEX IF NOT EXISTS idx_opening_lines_game ON opening_lines(game_id);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults (FKs ON, Row factory)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables + indexes if absent, and seed team_divisions.

    Safe to call repeatedly; idempotent.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    rows = [(team, conf, div) for team, (conf, div) in DIVISIONS.items()]
    conn.executemany(
        "INSERT OR REPLACE INTO team_divisions(team, conference, division) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()


def fetch_df(
    conn: sqlite3.Connection,
    sql: str,
    params: Sequence | None = None,
) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame."""
    return pd.read_sql_query(sql, conn, params=params)
