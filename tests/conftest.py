import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def memory_db():
    """Fresh in-memory SQLite connection. Foreign keys ON, Row factory enabled."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_db_path(tmp_path) -> Path:
    return tmp_path / "test.sqlite"
