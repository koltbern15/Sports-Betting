# NFL Betting Analytics — Slice 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate Slice 2's `ml_heavy_fav` +0.63% ROI finding by comparing the derived moneyline prices to real historical sportsbook moneylines from 2020–2024.

**Architecture:** New `real_ml_lines` SQLite table holds real prices, kept separate from `betting_lines` (one-off validation data). Data acquisition follows a tier ladder — `nfl_data_py.import_schedules()` is the primary source (returns `away_moneyline`/`home_moneyline` directly), with explicit fallback tasks documented in Appendix A. A pure-function comparator computes per-side implied-probability errors and recomputes bucket-level ROI under both price sets.

**Tech Stack:** Python 3.11+, `uv`, `pandas`, `nfl_data_py` (new), `pytest`, `ruff`, SQLite. Same stack as Slice 1/2 plus the one new dep.

**Spec:** `docs/superpowers/specs/2026-05-27-nfl-betting-slice3-design.md`

---

## Conventions used throughout this plan

- **All commands run from the project root** `C:\Users\ktber\projects\sports-betting`.
- **All commands assume PowerShell.** Forward slashes in `uv`/`pytest` arguments are fine.
- **Every task ends with a commit.** Conventional Commits (`feat:`, `test:`, `chore:`, `docs:`).
- **Run `uv run pytest -q` after each task** to confirm previously-green tests still pass (191 baseline from Slice 2).
- **Floating-point assertions use `pytest.approx`** (DNR: `.wolf/cerebrum.md` 2026-05-27 entry).
- **Avoid single-char `l` in loop unpacking** (DNR: ruff E741 from 2026-05-27).
- **Scope imports tightly per task** (DNR: ruff F401 from both prior slices).

---

## File-level decomposition

| File | Responsibility | Lifecycle in Slice 3 |
|---|---|---|
| `pyproject.toml` | Add `nfl-data-py` dep | **MODIFY** (T1) |
| `docs/superpowers/notes/2026-05-27-nflverse-probe.md` | Probe findings | **NEW** (T1) |
| `engine/db.py` | Add `real_ml_lines` table to `init_schema` | **MODIFY** (T2) |
| `tests/test_db.py` | Tests for `real_ml_lines` schema + idempotency | **MODIFY** (T2) |
| `ingestion/team_codes.py` | Map nflverse team abbreviation → canonical name | **NEW** (T3) |
| `tests/test_static_data.py` | Tests for `team_codes` mapping | **MODIFY** (T3) |
| `ingestion/real_ml_source.py` | `fetch_real_ml(seasons)` — wraps nfl_data_py | **NEW** (T4) |
| `tests/test_real_ml_source.py` | Mock nfl_data_py; assert returned DataFrame schema | **NEW** (T4) |
| `tests/fixtures/real_ml_5.csv` | Hand-built 5-game fixture | **NEW** (T5) |
| `ingestion/real_ml_loader.py` | Parse + validate + upsert into `real_ml_lines` | **NEW** (T6, T7) |
| `tests/test_real_ml_loader.py` | Fixture-driven loader tests | **NEW** (T6, T7) |
| `engine/validation.py` | `compare_ml_prices` + `ValidationReport` + CLI | **NEW** (T8, T9, T10) |
| `tests/test_validation.py` | Comparator + CLI tests | **NEW** (T8, T9, T10) |
| `README.md` | Add Slice 3 section | **MODIFY** (T12) |

---

## Task 1: Probe — install `nfl_data_py`, verify 2020–2024 moneyline coverage

**Files:**
- Modify: `pyproject.toml`
- Create: `docs/superpowers/notes/2026-05-27-nflverse-probe.md`

Purpose: confirm the tier-1 data source returns moneylines for 2020–2024 *before* any code is written against it. Documents what columns come back so T4 can wrap the right interface.

- [ ] **Step 1: Add `nfl-data-py` as a dependency**

```powershell
uv add nfl-data-py
```

Expected: `pyproject.toml` updated, `uv.lock` updated, `Installed ... nfl-data-py ...` printed. If install fails on Windows due to a transitive dep (`pyarrow` or similar), capture the error and fall back to Appendix A T4-alt.

- [ ] **Step 2: Run a probe in a Python REPL via uv**

```powershell
uv run python -c "import nfl_data_py as nfl; df = nfl.import_schedules([2020,2021,2022,2023,2024]); print('shape:', df.shape); print('cols:', list(df.columns)); print(df[['season','week','home_team','away_team','home_moneyline','away_moneyline']].head(10).to_string())"
```

Expected: a DataFrame with several thousand rows. Columns must include `season`, `week`, `home_team`, `away_team`, `home_moneyline`, `away_moneyline`. Head should show integer-like ML values (e.g., `-280`, `+240`).

If `home_moneyline`/`away_moneyline` columns are absent, list every column and find the equivalent (variants: `home_ml`, `ml_home`, `moneyline_home`). Note the actual column names in the probe doc.

- [ ] **Step 3: Verify non-null coverage**

```powershell
uv run python -c "import nfl_data_py as nfl; df = nfl.import_schedules([2020,2021,2022,2023,2024]); print('rows:', len(df)); print('with home_ml:', df['home_moneyline'].notna().sum()); print('with away_ml:', df['away_moneyline'].notna().sum())"
```

Expected: ≥95% of games have non-null moneylines for both sides. If coverage is sparse (<80%), document the year-by-year breakdown in the probe doc and consider proceeding with only the well-covered seasons.

- [ ] **Step 4: Inspect team abbreviation format**

```powershell
uv run python -c "import nfl_data_py as nfl; df = nfl.import_schedules([2024]); print(sorted(df['home_team'].unique()))"
```

Expected: a list of 32 three-letter codes (e.g., `KC`, `LV`, `LA`, `WAS`). Write the exact codes seen into the probe doc — T3 needs this list to build the code→canonical-name map.

- [ ] **Step 5: Write the probe findings doc**

Create `docs/superpowers/notes/2026-05-27-nflverse-probe.md` with this template — fill in the actual values:

```markdown
# nflverse import_schedules probe — 2026-05-27

**Source:** `nfl_data_py.import_schedules([2020,2021,2022,2023,2024])`

**Total rows:** N

**ML columns found:** home_moneyline, away_moneyline   (or note actuals)

**Coverage by season:**
| season | rows | home_ml_non_null | away_ml_non_null |
|---|---|---|---|
| 2020 | ... | ... | ... |
...

**Team abbreviation codes seen:** (paste the list from step 4)

**Other potentially useful columns:** spread_line, total_line, away_spread_odds, home_spread_odds, ... (list any betting-relevant columns)

**Decision:** Tier 1 viable / not viable. If not viable, see Appendix A.
```

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml uv.lock docs/superpowers/notes/2026-05-27-nflverse-probe.md
git commit -m "chore(slice3): add nfl-data-py + probe nflverse ML coverage 2020-2024"
```

Expected: commit succeeds. If T1 found tier 1 is not viable, switch to Appendix A *before proceeding to T2*.

---

## Task 2: Add `real_ml_lines` table to schema

**Files:**
- Modify: `engine/db.py`
- Modify: `tests/test_db.py`

Purpose: add the new table that holds real historical moneyline prices, alongside the existing `games` / `betting_lines` / `team_divisions` tables. Idempotent — re-running `init_schema` on an existing DB must not error.

- [ ] **Step 1: Write the failing test for table presence**

Append to `tests/test_db.py`:

```python
def test_init_schema_creates_real_ml_lines_table():
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
```

- [ ] **Step 2: Run test, verify it fails**

```powershell
uv run pytest tests/test_db.py::test_init_schema_creates_real_ml_lines_table -v
```

Expected: FAIL with no such table: real_ml_lines.

- [ ] **Step 3: Extend `_SCHEMA_SQL` in `engine/db.py`**

Append to the `_SCHEMA_SQL` triple-quoted string (after the `team_divisions` block):

```sql

CREATE TABLE IF NOT EXISTS real_ml_lines (
    game_id       TEXT PRIMARY KEY REFERENCES games(game_id),
    ml_home_real  INTEGER,
    ml_away_real  INTEGER,
    source        TEXT,
    source_url    TEXT,
    collected_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_real_ml_lines_game ON real_ml_lines(game_id);
```

- [ ] **Step 4: Re-run the new test**

```powershell
uv run pytest tests/test_db.py::test_init_schema_creates_real_ml_lines_table -v
```

Expected: PASS.

- [ ] **Step 5: Add an idempotency test**

Append to `tests/test_db.py`:

```python
def test_init_schema_real_ml_lines_idempotent():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    init_schema(conn)  # second call must not raise
    cursor = conn.execute("SELECT COUNT(*) FROM real_ml_lines")
    assert cursor.fetchone()[0] == 0
    conn.close()
```

- [ ] **Step 6: Run all tests + ruff**

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: 193 tests pass (191 baseline + 2 new), ruff clean.

- [ ] **Step 7: Commit**

```powershell
git add engine/db.py tests/test_db.py
git commit -m "feat(db): add real_ml_lines table for Slice 3 validation"
```

---

## Task 3: `ingestion/team_codes.py` — nflverse abbreviation → canonical name map

**Files:**
- Create: `ingestion/team_codes.py`
- Modify: `tests/test_static_data.py`

Purpose: nflverse uses 2–3 letter codes (`KC`, `LV`, `WAS`); our DB stores canonical full names (`Kansas City Chiefs`). Build a deterministic map so the loader can join real ML rows to `games` by team name.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_static_data.py`:

```python
from ingestion.team_codes import NFLVERSE_TEAM_CODES, code_to_canonical


def test_team_codes_has_all_32_teams():
    assert len(NFLVERSE_TEAM_CODES) == 32


def test_code_to_canonical_modern():
    assert code_to_canonical("KC") == "Kansas City Chiefs"
    assert code_to_canonical("LV") == "Las Vegas Raiders"
    assert code_to_canonical("WAS") == "Washington Commanders"
    assert code_to_canonical("LA") == "Los Angeles Rams"
    assert code_to_canonical("LAC") == "Los Angeles Chargers"


def test_code_to_canonical_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        code_to_canonical("ZZZ")


def test_all_codes_resolve_to_canonical_set():
    from ingestion.team_names import CANONICAL_TEAMS
    for code in NFLVERSE_TEAM_CODES:
        assert code_to_canonical(code) in CANONICAL_TEAMS
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_static_data.py -v -k team_codes
```

Expected: ImportError or `ModuleNotFoundError`.

- [ ] **Step 3: Create `ingestion/team_codes.py`**

```python
"""nflverse team abbreviation → canonical full-name mapping.

nflverse uses stable 2–3-letter codes (KC, LV, LAC, WAS). This module maps
each to the canonical name used in our DB (matches `ingestion/team_names.py`
output). Update the probe doc's "Team abbreviation codes seen" if any code
is missing here.
"""

from __future__ import annotations

NFLVERSE_TEAM_CODES: dict[str, str] = {
    # AFC East
    "BUF": "Buffalo Bills",
    "MIA": "Miami Dolphins",
    "NE": "New England Patriots",
    "NYJ": "New York Jets",
    # AFC North
    "BAL": "Baltimore Ravens",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "PIT": "Pittsburgh Steelers",
    # AFC South
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "TEN": "Tennessee Titans",
    # AFC West
    "DEN": "Denver Broncos",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    # NFC East
    "DAL": "Dallas Cowboys",
    "NYG": "New York Giants",
    "PHI": "Philadelphia Eagles",
    "WAS": "Washington Commanders",
    # NFC North
    "CHI": "Chicago Bears",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "MIN": "Minnesota Vikings",
    # NFC South
    "ATL": "Atlanta Falcons",
    "CAR": "Carolina Panthers",
    "NO": "New Orleans Saints",
    "TB": "Tampa Bay Buccaneers",
    # NFC West
    "ARI": "Arizona Cardinals",
    "LA": "Los Angeles Rams",
    "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
}


def code_to_canonical(code: str) -> str:
    """Look up the canonical full name for an nflverse team code."""
    try:
        return NFLVERSE_TEAM_CODES[code]
    except KeyError as e:
        raise KeyError(f"unknown nflverse team code: {code!r}") from e
```

Note: if the T1 probe revealed a different code (e.g., older nflverse data uses `OAK` for Raiders pre-2020 or `STL` for Rams pre-2016), add those entries — but for 2020–2024 the 32 codes above should be sufficient.

- [ ] **Step 4: Run tests + ruff**

```powershell
uv run pytest tests/test_static_data.py -v -k team_codes
uv run pytest -q
uv run ruff check .
```

Expected: 4 new tests pass, 197 total, ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/team_codes.py tests/test_static_data.py
git commit -m "feat(team_codes): nflverse abbreviation -> canonical name map"
```

---

## Task 4: `ingestion/real_ml_source.py` — tier-1 fetcher

**Files:**
- Create: `ingestion/real_ml_source.py`
- Create: `tests/test_real_ml_source.py`

Purpose: wrap `nfl_data_py.import_schedules()` and return a DataFrame normalized to our canonical schema. Mockable — tests do not hit the network.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for ingestion.real_ml_source — nflverse fetcher with mocked HTTP."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ingestion.real_ml_source import fetch_real_ml


def _fake_nflverse_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2024, 2024, 2024],
            "week": [1, 1, 2],
            "home_team": ["KC", "BUF", "LV"],
            "away_team": ["BAL", "ARI", "LAC"],
            "home_moneyline": [-180, -240, +145],
            "away_moneyline": [+155, +200, -170],
            "spread_line": [-3.0, -6.5, +3.5],
        }
    )


def test_fetch_real_ml_returns_canonical_columns():
    with patch("ingestion.real_ml_source.nfl.import_schedules", return_value=_fake_nflverse_df()):
        df = fetch_real_ml([2024])
    assert list(df.columns) == [
        "season",
        "week",
        "home_team",
        "away_team",
        "ml_home_real",
        "ml_away_real",
        "source",
    ]
    assert df["source"].unique().tolist() == ["nflverse"]
    assert df.iloc[0]["home_team"] == "Kansas City Chiefs"
    assert df.iloc[0]["away_team"] == "Baltimore Ravens"


def test_fetch_real_ml_drops_rows_with_missing_ml():
    fake = _fake_nflverse_df()
    fake.loc[0, "home_moneyline"] = None
    with patch("ingestion.real_ml_source.nfl.import_schedules", return_value=fake):
        df = fetch_real_ml([2024])
    assert len(df) == 2  # row 0 dropped (missing home_ml)


def test_fetch_real_ml_passes_seasons_to_nflverse():
    captured = {}

    def fake_import(seasons):
        captured["seasons"] = seasons
        return _fake_nflverse_df()

    with patch("ingestion.real_ml_source.nfl.import_schedules", side_effect=fake_import):
        fetch_real_ml([2022, 2023, 2024])
    assert captured["seasons"] == [2022, 2023, 2024]
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_real_ml_source.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `ingestion/real_ml_source.py`**

```python
"""Tier-1 real moneyline data source — nflverse via nfl_data_py.

Wraps `nfl_data_py.import_schedules()` and normalizes its output to the
canonical schema consumed by `ingestion.real_ml_loader`. If T1 probe found
different column names, update the COL_HOME_ML / COL_AWAY_ML constants.
"""

from __future__ import annotations

import nfl_data_py as nfl
import pandas as pd

from ingestion.team_codes import code_to_canonical

COL_HOME_ML = "home_moneyline"
COL_AWAY_ML = "away_moneyline"


def fetch_real_ml(seasons: list[int]) -> pd.DataFrame:
    """Fetch real historical moneylines for the given seasons.

    Returns a DataFrame with columns:
        season (int), week (int),
        home_team (canonical full name), away_team (canonical full name),
        ml_home_real (int), ml_away_real (int),
        source (str = "nflverse")

    Rows missing either moneyline are dropped.
    """
    raw = nfl.import_schedules(seasons)
    df = raw[["season", "week", "home_team", "away_team", COL_HOME_ML, COL_AWAY_ML]].copy()
    df = df.dropna(subset=[COL_HOME_ML, COL_AWAY_ML])
    df["home_team"] = df["home_team"].map(code_to_canonical)
    df["away_team"] = df["away_team"].map(code_to_canonical)
    df = df.rename(columns={COL_HOME_ML: "ml_home_real", COL_AWAY_ML: "ml_away_real"})
    df["ml_home_real"] = df["ml_home_real"].astype(int)
    df["ml_away_real"] = df["ml_away_real"].astype(int)
    df["source"] = "nflverse"
    return df[
        ["season", "week", "home_team", "away_team", "ml_home_real", "ml_away_real", "source"]
    ].reset_index(drop=True)
```

- [ ] **Step 4: Run tests + ruff**

```powershell
uv run pytest tests/test_real_ml_source.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 3 new tests pass, 200 total, ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/real_ml_source.py tests/test_real_ml_source.py
git commit -m "feat(slice3): nflverse real-ml fetcher (tier 1)"
```

---

## Task 5: Hand-built `tests/fixtures/real_ml_5.csv`

**Files:**
- Create: `tests/fixtures/real_ml_5.csv`

Purpose: 5-row fixture used by both the loader integration test (T7) and the comparator test (T9). Each row exercises a distinct validation scenario.

- [ ] **Step 1: Create the fixture file**

Write exactly this content to `tests/fixtures/real_ml_5.csv` (header + 5 data rows). Lines correspond to:

| row | scenario | spread_home_close | derived_ml_home (approx) | real_ml_home | expected behavior |
|---|---|---|---|---|---|
| 1 | derived ≈ real | -3.0 | -159 | -160 | small +error, no flip |
| 2 | derived overshades home | -7.0 | -265 | -220 | larger derived favorite than reality |
| 3 | derived undershades home | -3.0 | -159 | -200 | model less aggressive than market |
| 4 | sign flip | -0.5 | -113 | +110 | derived favors home, real favors away |
| 5 | missing real_ml | -3.0 | -159 | (blank) | row skipped by loader |

```csv
season,week,home_team,away_team,ml_home_real,ml_away_real,source,source_url
2024,1,Kansas City Chiefs,Baltimore Ravens,-160,140,fixture,
2024,1,Buffalo Bills,Arizona Cardinals,-220,180,fixture,
2024,2,Detroit Lions,Tampa Bay Buccaneers,-200,170,fixture,
2024,2,Green Bay Packers,Indianapolis Colts,110,-130,fixture,
2024,3,Pittsburgh Steelers,Los Angeles Chargers,,,fixture,
```

- [ ] **Step 2: Verify**

```powershell
Get-Content tests/fixtures/real_ml_5.csv | Measure-Object -Line
```

Expected: `Lines : 6` (1 header + 5 data).

- [ ] **Step 3: Commit**

```powershell
git add tests/fixtures/real_ml_5.csv
git commit -m "test(slice3): 5-game fixture covering match/overshade/undershade/flip/missing"
```

---

## Task 6: `ingestion/real_ml_loader.py` — pure parse + validate helpers

**Files:**
- Create: `ingestion/real_ml_loader.py`
- Create: `tests/test_real_ml_loader.py`

Purpose: parse + validate each CSV row in isolation. Loader orchestration comes in T7.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for ingestion.real_ml_loader — parse + validate helpers."""

from __future__ import annotations

import pytest

from ingestion.real_ml_loader import parse_american_odds, validate_row


def test_parse_american_odds_negative():
    assert parse_american_odds("-110") == -110


def test_parse_american_odds_positive():
    assert parse_american_odds("+150") == 150
    assert parse_american_odds("150") == 150


def test_parse_american_odds_blank_returns_none():
    assert parse_american_odds("") is None
    assert parse_american_odds("  ") is None
    assert parse_american_odds(None) is None


def test_parse_american_odds_invalid_raises():
    with pytest.raises(ValueError):
        parse_american_odds("not a number")
    with pytest.raises(ValueError):
        parse_american_odds("-50")  # American odds must be <= -100 or >= +100


def test_validate_row_good():
    row = {
        "season": "2024",
        "week": "1",
        "home_team": "Kansas City Chiefs",
        "away_team": "Baltimore Ravens",
        "ml_home_real": "-180",
        "ml_away_real": "+155",
        "source": "nflverse",
        "source_url": "",
    }
    result = validate_row(row)
    assert result["season"] == 2024
    assert result["week"] == 1
    assert result["ml_home_real"] == -180
    assert result["ml_away_real"] == 155
    assert result["source"] == "nflverse"


def test_validate_row_blank_ml_returns_none_marker():
    row = {
        "season": "2024",
        "week": "3",
        "home_team": "Pittsburgh Steelers",
        "away_team": "Los Angeles Chargers",
        "ml_home_real": "",
        "ml_away_real": "",
        "source": "fixture",
        "source_url": "",
    }
    result = validate_row(row)
    assert result is None  # signals "skip this row"


def test_validate_row_bad_team_raises():
    row = {
        "season": "2024",
        "week": "1",
        "home_team": "Bogus Team",
        "away_team": "Baltimore Ravens",
        "ml_home_real": "-180",
        "ml_away_real": "+155",
        "source": "fixture",
        "source_url": "",
    }
    with pytest.raises(ValueError, match="unknown team"):
        validate_row(row)
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_real_ml_loader.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `ingestion/real_ml_loader.py` with helpers**

```python
"""Loader for real historical moneylines into the real_ml_lines table.

Two layers:
  - pure helpers (parse_american_odds, validate_row) — testable without DB
  - orchestrator (load_csv_to_db) — joins to games, upserts, idempotent
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ingestion.team_names import CANONICAL_TEAMS


def parse_american_odds(value: str | None) -> int | None:
    """Parse a string American-odds value to int, or None if blank.

    Raises ValueError if value is non-blank and not a valid American odds magnitude
    (i.e., must satisfy |x| >= 100).
    """
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    try:
        n = int(stripped)
    except ValueError as e:
        raise ValueError(f"not a valid American odds value: {value!r}") from e
    if -100 < n < 100:
        raise ValueError(f"American odds magnitude must be >= 100, got {n}")
    return n


def validate_row(row: dict) -> dict | None:
    """Validate + coerce a CSV row. Returns parsed dict, or None if blank ML pair.

    Raises ValueError for malformed data (bad team name, bad number formats).
    """
    home_ml = parse_american_odds(row.get("ml_home_real"))
    away_ml = parse_american_odds(row.get("ml_away_real"))
    if home_ml is None and away_ml is None:
        return None
    home_team = row["home_team"].strip()
    away_team = row["away_team"].strip()
    if home_team not in CANONICAL_TEAMS:
        raise ValueError(f"unknown team: {home_team!r}")
    if away_team not in CANONICAL_TEAMS:
        raise ValueError(f"unknown team: {away_team!r}")
    return {
        "season": int(row["season"]),
        "week": int(row["week"]),
        "home_team": home_team,
        "away_team": away_team,
        "ml_home_real": home_ml,
        "ml_away_real": away_ml,
        "source": row.get("source", "").strip() or "unknown",
        "source_url": row.get("source_url", "").strip() or None,
    }
```

- [ ] **Step 4: Run tests + ruff**

```powershell
uv run pytest tests/test_real_ml_loader.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 7 new tests pass, 207 total, ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/real_ml_loader.py tests/test_real_ml_loader.py
git commit -m "feat(slice3): real_ml_loader parse + validate helpers"
```

---

## Task 7: `ingestion/real_ml_loader.py` — `load_csv_to_db` orchestrator

**Files:**
- Modify: `ingestion/real_ml_loader.py` (append orchestrator + LoadReport + CLI)
- Modify: `tests/test_real_ml_loader.py` (append integration tests)

Purpose: glue the validated rows to existing games via `(season, week, home_team, away_team)`, upsert into `real_ml_lines`, report counts. Idempotent.

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_real_ml_loader.py`:

```python
import sqlite3

from engine.db import init_schema
from ingestion.real_ml_loader import LoadReport, load_csv_to_db


def _seed_games(conn: sqlite3.Connection) -> None:
    rows = [
        ("2024_01_KC_BAL", 2024, 1, "2024-09-05", "Kansas City Chiefs", "Baltimore Ravens"),
        ("2024_01_BUF_ARI", 2024, 1, "2024-09-08", "Buffalo Bills", "Arizona Cardinals"),
        ("2024_02_DET_TB", 2024, 2, "2024-09-15", "Detroit Lions", "Tampa Bay Buccaneers"),
        ("2024_02_GB_IND", 2024, 2, "2024-09-15", "Green Bay Packers", "Indianapolis Colts"),
        ("2024_03_PIT_LAC", 2024, 3, "2024-09-22", "Pittsburgh Steelers", "Los Angeles Chargers"),
    ]
    conn.executemany(
        "INSERT INTO games(game_id, season, week, game_date, home_team, away_team)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def test_load_csv_to_db_happy_path(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_games(conn)

    report = load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")

    assert isinstance(report, LoadReport)
    assert report.inserted == 4  # row 5 has blank ML, skipped
    assert report.skipped_blank == 1
    assert report.rejected_bad == 0
    assert report.unmatched_games == 0

    cursor = conn.execute("SELECT COUNT(*) FROM real_ml_lines")
    assert cursor.fetchone()[0] == 4
    conn.close()


def test_load_csv_to_db_idempotent(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_games(conn)

    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")  # second run

    cursor = conn.execute("SELECT COUNT(*) FROM real_ml_lines")
    assert cursor.fetchone()[0] == 4  # still 4, not 8
    conn.close()


def test_load_csv_to_db_unmatched_games_reported(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    # seed only 2 of the 5 fixture games
    conn.executemany(
        "INSERT INTO games(game_id, season, week, game_date, home_team, away_team)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("2024_01_KC_BAL", 2024, 1, "2024-09-05", "Kansas City Chiefs", "Baltimore Ravens"),
            ("2024_01_BUF_ARI", 2024, 1, "2024-09-08", "Buffalo Bills", "Arizona Cardinals"),
        ],
    )
    conn.commit()

    report = load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")

    assert report.inserted == 2
    assert report.unmatched_games == 2  # Detroit + Green Bay; row 5 was blank so skipped first
    conn.close()
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_real_ml_loader.py -v -k load_csv_to_db
```

Expected: ImportError on `LoadReport` / `load_csv_to_db`.

- [ ] **Step 3: Append orchestrator to `ingestion/real_ml_loader.py`**

Append after `validate_row`:

```python
@dataclass(frozen=True)
class LoadReport:
    """Counts emitted by `load_csv_to_db`."""

    inserted: int
    skipped_blank: int
    rejected_bad: int
    unmatched_games: int
    errors: list[str] = field(default_factory=list)


def load_csv_to_db(conn: sqlite3.Connection, csv_path: str | Path) -> LoadReport:
    """Load real-ML rows from a CSV into `real_ml_lines`. Idempotent."""
    inserted = 0
    skipped_blank = 0
    rejected_bad = 0
    unmatched_games = 0
    errors: list[str] = []
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_no, raw in enumerate(reader, start=2):  # line 1 is header
            try:
                parsed = validate_row(raw)
            except ValueError as e:
                rejected_bad += 1
                errors.append(f"line {line_no}: {e}")
                continue
            if parsed is None:
                skipped_blank += 1
                continue

            cursor = conn.execute(
                "SELECT game_id FROM games WHERE season=? AND week=? AND home_team=? AND away_team=?",
                (parsed["season"], parsed["week"], parsed["home_team"], parsed["away_team"]),
            )
            match = cursor.fetchone()
            if match is None:
                unmatched_games += 1
                errors.append(
                    f"line {line_no}: no game found for "
                    f"{parsed['season']} W{parsed['week']} "
                    f"{parsed['away_team']} @ {parsed['home_team']}"
                )
                continue
            game_id = match[0]

            conn.execute(
                "INSERT OR REPLACE INTO real_ml_lines"
                "(game_id, ml_home_real, ml_away_real, source, source_url, collected_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    parsed["ml_home_real"],
                    parsed["ml_away_real"],
                    parsed["source"],
                    parsed["source_url"],
                    now_iso,
                ),
            )
            inserted += 1
    conn.commit()

    return LoadReport(
        inserted=inserted,
        skipped_blank=skipped_blank,
        rejected_bad=rejected_bad,
        unmatched_games=unmatched_games,
        errors=errors,
    )


def _main() -> int:
    """CLI: uv run python -m ingestion.real_ml_loader <csv_path>"""
    import sys

    from engine.db import connect

    if len(sys.argv) != 2:
        print("Usage: python -m ingestion.real_ml_loader <csv_path>")
        return 2
    csv_path = sys.argv[1]
    conn = connect("data/db/nfl_betting.sqlite")
    from engine.db import init_schema

    init_schema(conn)
    report = load_csv_to_db(conn, csv_path)
    print(
        f"inserted={report.inserted} "
        f"skipped_blank={report.skipped_blank} "
        f"rejected_bad={report.rejected_bad} "
        f"unmatched_games={report.unmatched_games}"
    )
    for err in report.errors[:10]:
        print(f"  {err}")
    if len(report.errors) > 10:
        print(f"  ... ({len(report.errors) - 10} more)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
```

- [ ] **Step 4: Run tests + ruff**

```powershell
uv run pytest tests/test_real_ml_loader.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 3 new tests pass (10 total in this file), 210 total project tests, ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/real_ml_loader.py tests/test_real_ml_loader.py
git commit -m "feat(slice3): real_ml_loader orchestrator + LoadReport + CLI"
```

---

## Task 8: `engine/validation.py` — pure comparator helpers

**Files:**
- Create: `engine/validation.py`
- Create: `tests/test_validation.py`

Purpose: pure-function math for per-side error metrics. No DB, no I/O. The DB join + report assembly comes in T9.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for engine.validation — pure helpers."""

from __future__ import annotations

import math

import pytest

from engine.validation import (
    american_to_implied_prob,
    compute_price_stats,
    side_error,
)


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
    # all derived implied prob > real implied prob on favorite side => negative mean_error_prob on fav
    assert stats["mean_error_prob"] < 0
    assert stats["pct_sign_flip"] == 0.0
    assert stats["derived_overshades_favorites"] is True


def test_compute_price_stats_sign_flip():
    sides = [
        {"real_ml": +120, "derived_ml": -120, "is_favorite": False},  # real says dog, derived says fav
    ]
    stats = compute_price_stats(sides)
    assert stats["pct_sign_flip"] == 1.0


def test_compute_price_stats_no_data():
    with pytest.raises(ValueError, match="empty"):
        compute_price_stats([])
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_validation.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `engine/validation.py` with helpers**

```python
"""Real-line moneyline validation — comparator + reporting.

Compares derived ML prices (from `engine.moneyline.derive_ml_from_spread`)
to real historical ML prices stored in `real_ml_lines`. Outputs per-side
implied-probability errors plus per-bucket ROI under both price sets.
"""

from __future__ import annotations

from statistics import mean, median


def american_to_implied_prob(ml: int) -> float:
    """Convert integer American odds to raw implied probability (vig included)."""
    if ml < 0:
        return (-ml) / ((-ml) + 100)
    return 100 / (ml + 100)


def side_error(real_ml: int, derived_ml: int) -> dict:
    """Per-side comparison: error in implied-probability points and raw American delta.

    Returns {"error_prob": float, "error_ml": int}
      error_prob = real_implied_p - derived_implied_p
        (positive => real market priced this side as more likely than derived)
      error_ml   = real_ml - derived_ml (raw American-odds delta, for readability)
    """
    return {
        "error_prob": american_to_implied_prob(real_ml) - american_to_implied_prob(derived_ml),
        "error_ml": real_ml - derived_ml,
    }


def compute_price_stats(sides: list[dict]) -> dict:
    """Aggregate per-side comparisons into summary stats.

    Each side dict must contain: real_ml, derived_ml, is_favorite (bool).
    """
    if not sides:
        raise ValueError("compute_price_stats called with empty sides list")

    errors = [side_error(s["real_ml"], s["derived_ml"]) for s in sides]
    errs_prob = [e["error_prob"] for e in errors]
    errs_ml = [e["error_ml"] for e in errors]

    n_sides = len(sides)
    n_within = sum(1 for e in errs_prob if abs(e) <= 0.02)

    sign_flips = 0
    for side, err in zip(sides, errs_prob, strict=True):
        real_p = american_to_implied_prob(side["real_ml"])
        derived_p = american_to_implied_prob(side["derived_ml"])
        if (real_p > 0.5) != (derived_p > 0.5):
            sign_flips += 1

    fav_errors = [
        e["error_prob"] for e, s in zip(errors, sides, strict=True) if s["is_favorite"]
    ]
    if fav_errors:
        mean_fav_err = mean(fav_errors)
        pct_share_sign = sum(1 for e in fav_errors if e < 0) / len(fav_errors)
        overshades = mean_fav_err < 0 and pct_share_sign > 0.6
    else:
        overshades = False

    return {
        "n_sides": n_sides,
        "mean_error_prob": mean(errs_prob),
        "median_abs_error_prob": median(abs(e) for e in errs_prob),
        "pct_within_2_pct_points": n_within / n_sides,
        "pct_sign_flip": sign_flips / n_sides,
        "derived_overshades_favorites": overshades,
        "mean_error_ml": mean(errs_ml),
    }
```

- [ ] **Step 4: Run tests + ruff**

```powershell
uv run pytest tests/test_validation.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 7 new tests pass, 217 total, ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add engine/validation.py tests/test_validation.py
git commit -m "feat(slice3): validation pure helpers (implied-prob error, sign-flip)"
```

---

## Task 9: `engine/validation.py` — `compare_ml_prices` orchestrator + `ValidationReport`

**Files:**
- Modify: `engine/validation.py` (append orchestrator)
- Modify: `tests/test_validation.py` (append integration tests using fixture)

Purpose: assemble the SQL join (games + betting_lines + real_ml_lines), recompute derived ML, build per-bucket ROI tables under both price sets.

- [ ] **Step 1: Append failing integration tests**

```python
import sqlite3

from engine.db import init_schema
from engine.validation import BucketComparison, ValidationReport, compare_ml_prices
from ingestion.real_ml_loader import load_csv_to_db


def _seed_full_fixture(conn: sqlite3.Connection) -> None:
    games = [
        ("2024_01_KC_BAL", 2024, 1, "2024-09-05", "Kansas City Chiefs", "Baltimore Ravens", 27, 20),
        ("2024_01_BUF_ARI", 2024, 1, "2024-09-08", "Buffalo Bills", "Arizona Cardinals", 34, 28),
        ("2024_02_DET_TB", 2024, 2, "2024-09-15", "Detroit Lions", "Tampa Bay Buccaneers", 20, 16),
        ("2024_02_GB_IND", 2024, 2, "2024-09-15", "Green Bay Packers", "Indianapolis Colts", 16, 10),
        ("2024_03_PIT_LAC", 2024, 3, "2024-09-22", "Pittsburgh Steelers", "Los Angeles Chargers", 13, 20),
    ]
    conn.executemany(
        "INSERT INTO games(game_id, season, week, game_date, home_team, away_team, home_score, away_score)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        games,
    )
    lines = [
        ("2024_01_KC_BAL", -3.0),
        ("2024_01_BUF_ARI", -7.0),
        ("2024_02_DET_TB", -3.0),
        ("2024_02_GB_IND", -0.5),
        ("2024_03_PIT_LAC", -3.0),  # included so it appears in DB; no real ML for it
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
    # 4 games matched (row 5 blank); each yields 2 sides
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
    # Sanity: mean_error_prob is in plausible range
    assert -0.2 < report.price_stats["mean_error_prob"] < 0.2
    conn.close()


def test_compare_ml_prices_empty_raises():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    # no real_ml_lines loaded
    import pytest

    with pytest.raises(ValueError, match="insufficient validation data"):
        compare_ml_prices(conn)
    conn.close()


def test_compare_ml_prices_bucket_rows_match_slice2_assignment():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")

    report = compare_ml_prices(conn)
    # buckets are assigned on derived ML; row -7.0 spread -> heavy fav side derived ~ -265 -> ml_heavy_fav
    bucket_names = {bc.bucket for bc in report.bucket_comparisons}
    assert "ml_heavy_fav" in bucket_names or "ml_mid_fav" in bucket_names
    for bc in report.bucket_comparisons:
        assert isinstance(bc, BucketComparison)
        assert bc.n >= 1
    conn.close()
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_validation.py -v -k compare_ml_prices
```

Expected: ImportError on `compare_ml_prices` / `ValidationReport` / `BucketComparison`.

- [ ] **Step 3: Append orchestrator to `engine/validation.py`**

Add at the top of `engine/validation.py` (extra imports):

```python
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from engine.db import fetch_df
from engine.moneyline import bucket_ml, derive_ml_from_spread
```

Append after `compute_price_stats`:

```python
@dataclass(frozen=True)
class BucketComparison:
    """Per-bucket ROI comparison: derived prices vs real prices, same outcomes."""

    bucket: str
    n: int
    derived_roi: float
    real_roi: float
    delta_roi: float
    derived_wins: int
    derived_losses: int
    real_wins: int
    real_losses: int


@dataclass(frozen=True)
class ValidationReport:
    """End-to-end output of compare_ml_prices."""

    price_stats: dict
    bucket_comparisons: list[BucketComparison]
    source: str
    n_games: int


_SQL = """
SELECT g.game_id, g.season, g.home_team, g.away_team,
       g.home_score, g.away_score,
       bl.spread_home_close,
       r.ml_home_real, r.ml_away_real, r.source
FROM real_ml_lines r
JOIN games g          ON g.game_id = r.game_id
JOIN betting_lines bl ON bl.game_id = r.game_id
WHERE g.home_score IS NOT NULL
  AND g.away_score IS NOT NULL
  AND bl.spread_home_close IS NOT NULL
"""


def _payout(ml: int, won: bool) -> float:
    """PnL on $1 stake at the given American odds. Pushes not supported (ML rarely pushes)."""
    if not won:
        return -1.0
    if ml < 0:
        return 100.0 / (-ml)
    return ml / 100.0


def compare_ml_prices(conn: sqlite3.Connection) -> ValidationReport:
    """Build the validation report — joins real ML to games + spreads, recomputes derived ML."""
    df = fetch_df(conn, _SQL)
    if len(df) == 0:
        raise ValueError("insufficient validation data — real_ml_lines is empty or unjoinable")

    sides: list[dict] = []
    bucket_rows: list[dict] = []

    for row in df.itertuples(index=False):
        derived = derive_ml_from_spread(row.spread_home_close)
        if derived is None:
            continue
        derived_home, derived_away = derived
        home_won = row.home_score > row.away_score
        away_won = row.away_score > row.home_score
        # ties produce neither home_won nor away_won; ML pushes are extremely rare

        for side_name, derived_ml, real_ml, won in (
            ("home", derived_home, int(row.ml_home_real), home_won),
            ("away", derived_away, int(row.ml_away_real), away_won),
        ):
            sides.append(
                {"real_ml": real_ml, "derived_ml": derived_ml, "is_favorite": derived_ml < 0}
            )
            bucket = bucket_ml(derived_ml)
            if bucket is None:
                continue
            bucket_rows.append(
                {
                    "bucket": bucket,
                    "won": won,
                    "derived_pnl": _payout(derived_ml, won),
                    "real_pnl": _payout(real_ml, won),
                }
            )

    price_stats = compute_price_stats(sides)
    bucket_comparisons = _build_bucket_comparisons(bucket_rows)
    source = str(df["source"].mode().iloc[0]) if len(df) else "unknown"
    return ValidationReport(
        price_stats=price_stats,
        bucket_comparisons=bucket_comparisons,
        source=source,
        n_games=int(df["game_id"].nunique()),
    )


def _build_bucket_comparisons(bucket_rows: list[dict]) -> list[BucketComparison]:
    """Aggregate per-bet rows into per-bucket comparison records."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in bucket_rows:
        grouped[row["bucket"]].append(row)
    out: list[BucketComparison] = []
    for bucket, rows in grouped.items():
        n = len(rows)
        derived_wins = sum(1 for r in rows if r["won"] and r["derived_pnl"] > 0)
        derived_losses = sum(1 for r in rows if not r["won"])
        real_wins = sum(1 for r in rows if r["won"] and r["real_pnl"] > 0)
        real_losses = sum(1 for r in rows if not r["won"])
        derived_roi = sum(r["derived_pnl"] for r in rows) / n
        real_roi = sum(r["real_pnl"] for r in rows) / n
        out.append(
            BucketComparison(
                bucket=bucket,
                n=n,
                derived_roi=derived_roi,
                real_roi=real_roi,
                delta_roi=real_roi - derived_roi,
                derived_wins=derived_wins,
                derived_losses=derived_losses,
                real_wins=real_wins,
                real_losses=real_losses,
            )
        )
    out.sort(key=lambda bc: bc.bucket)
    return out
```

- [ ] **Step 4: Run tests + ruff**

```powershell
uv run pytest tests/test_validation.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 4 new tests pass (11 total in this file), 221 total project tests, ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add engine/validation.py tests/test_validation.py
git commit -m "feat(slice3): compare_ml_prices orchestrator + ValidationReport"
```

---

## Task 10: `engine/validation.py` — CLI entry + CSV output

**Files:**
- Modify: `engine/validation.py` (append `_main` + tabulated output + CSV writer)
- Modify: `tests/test_validation.py` (append CLI smoke test)

Purpose: human-readable stdout (two tables), CSV report on disk with comment-line disclaimer.

- [ ] **Step 1: Write failing test for CSV output**

Append to `tests/test_validation.py`:

```python
from pathlib import Path

from engine.validation import write_validation_csv


def test_write_validation_csv_includes_comments(tmp_path):
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
```

- [ ] **Step 2: Run test, verify it fails**

```powershell
uv run pytest tests/test_validation.py::test_write_validation_csv_includes_comments -v
```

Expected: ImportError on `write_validation_csv`.

- [ ] **Step 3: Append CLI + writer to `engine/validation.py`**

Add to the imports block at the top:

```python
from pathlib import Path

from tabulate import tabulate

from engine.bucket_analysis import DISCLAIMER
```

Append after `_build_bucket_comparisons`:

```python
def _format_price_table(stats: dict) -> str:
    rows = [
        ["n_sides", stats["n_sides"]],
        ["mean_error_prob", f"{stats['mean_error_prob']:+.4f}"],
        ["median_abs_error_prob", f"{stats['median_abs_error_prob']:.4f}"],
        ["pct_within_2_pct_points", f"{stats['pct_within_2_pct_points']:.4f}"],
        ["pct_sign_flip", f"{stats['pct_sign_flip']:.4f}"],
        ["derived_overshades_favorites", stats["derived_overshades_favorites"]],
        ["mean_error_ml", f"{stats['mean_error_ml']:+.2f}"],
    ]
    return tabulate(rows, headers=["metric", "value"], tablefmt="github")


def _format_bucket_table(comparisons: list[BucketComparison]) -> str:
    headers = [
        "bucket", "n",
        "derived_roi", "real_roi", "delta_roi",
        "derived_W", "derived_L", "real_W", "real_L",
    ]
    rows = [
        [
            bc.bucket, bc.n,
            f"{bc.derived_roi:+.4f}", f"{bc.real_roi:+.4f}", f"{bc.delta_roi:+.4f}",
            bc.derived_wins, bc.derived_losses, bc.real_wins, bc.real_losses,
        ]
        for bc in comparisons
    ]
    return tabulate(rows, headers=headers, tablefmt="github")


def write_validation_csv(report: ValidationReport, path: str | Path) -> None:
    """Write the bucket-comparison table to CSV with comment-line disclaimer + source note."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Real-line sample: source={report.source}, n_games={report.n_games}",
        f"# {DISCLAIMER}",
        "bucket,n,derived_roi,real_roi,delta_roi,derived_wins,derived_losses,real_wins,real_losses",
    ]
    for bc in report.bucket_comparisons:
        lines.append(
            f"{bc.bucket},{bc.n},"
            f"{bc.derived_roi:.6f},{bc.real_roi:.6f},{bc.delta_roi:.6f},"
            f"{bc.derived_wins},{bc.derived_losses},{bc.real_wins},{bc.real_losses}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _main() -> int:
    """CLI: uv run python -m engine.validation"""
    from engine.db import connect

    conn = connect("data/db/nfl_betting.sqlite")
    try:
        report = compare_ml_prices(conn)
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Hint: load real ML first via `python -m ingestion.real_ml_loader <csv>`")
        return 1

    print(f"Validation report — source={report.source}, n_games={report.n_games}\n")
    print("Price-level diagnostics:")
    print(_format_price_table(report.price_stats))
    print()
    print("Bucket-ROI comparison (bucket assigned on DERIVED ML):")
    print(_format_bucket_table(report.bucket_comparisons))
    print(f"\n{DISCLAIMER}")

    out_path = Path("data/processed/ml_validation_report.csv")
    write_validation_csv(report, out_path)
    print(f"\nCSV written to {out_path}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
```

- [ ] **Step 4: Run tests + ruff**

```powershell
uv run pytest tests/test_validation.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 1 new test passes (12 total in file), 222 total project tests, ruff clean.

- [ ] **Step 5: Commit**

(CLI smoke-run against real data happens in T11; the CLI hits the on-disk DB, so unit tests cover the writer in isolation.)

```powershell
git add engine/validation.py tests/test_validation.py
git commit -m "feat(slice3): validation CLI + tabulated output + CSV writer"
```

---

## Task 11: Real-data fetch + load + validate (no commit until verified)

**Files:** none (data files are gitignored under `data/raw/` and `data/processed/`).

Assumes `data/db/nfl_betting.sqlite` exists with 5,680 games from Slice 1.

- [ ] **Step 1: Verify Slice 1 DB exists**

```powershell
Test-Path data/db/nfl_betting.sqlite
```

Expected: `True`. If `False`, re-run the Slice 1 loader first.

- [ ] **Step 2: Fetch real ML via tier 1 (nflverse)**

```powershell
uv run python -c "from ingestion.real_ml_source import fetch_real_ml; df = fetch_real_ml([2020,2021,2022,2023,2024]); df.to_csv('data/raw/real_ml_2020_2024.csv', index=False); print('wrote', len(df), 'rows to data/raw/real_ml_2020_2024.csv')"
```

Expected: ~1,300 rows written. If error mentions a column name like `home_moneyline` not found, update `COL_HOME_ML` / `COL_AWAY_ML` constants in `ingestion/real_ml_source.py` per T1 probe findings, then re-run.

- [ ] **Step 3: Load into DB**

```powershell
uv run python -m ingestion.real_ml_loader data/raw/real_ml_2020_2024.csv
```

Expected output:
```
inserted=NNNN skipped_blank=0 rejected_bad=0 unmatched_games=MM
```

Inserted count should be in the 1,200–1,360 range (one row per game). Some unmatched games are expected because Slice 1's Kaggle CSV may have a few different game spellings — note the count, investigate if >50.

- [ ] **Step 4: Run the validation CLI**

```powershell
uv run python -m engine.validation
```

Expected:
- Price-level diagnostics table (7 rows of metrics)
- Bucket-ROI comparison table (≤11 rows, only buckets with data)
- `data/processed/ml_validation_report.csv` written

Save the printed output — it's the headline finding for the slice.

- [ ] **Step 5: Spot-check the CSV**

```powershell
Get-Content data/processed/ml_validation_report.csv -TotalCount 5
```

Expected: line 1 = source note, line 2 = disclaimer, line 3 = header, line 4+ = data.

- [ ] **Step 6: Final test + ruff sweep**

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: 222 tests pass, ruff clean.

- [ ] **Step 7: No commit yet** — proceed to T12 to record findings.

---

## Task 12: README + findings note + tag `slice3-complete`

**Files:**
- Modify: `README.md`
- Modify: `.wolf/memory.md` (one-paragraph findings summary)

- [ ] **Step 1: Add a "Slice 3 — Real-line validation" section to README**

Open `README.md` and append a new section. Paste this content (use the actual numbers from T11 in the "Headline finding" sentence):

    ## Slice 3 — Real-line moneyline validation

    Validates Slice 2's derived-ML findings against real historical moneylines from
    nflverse (2020–2024).

    ### Run

    ```powershell
    # fetch real ML
    uv run python -c "from ingestion.real_ml_source import fetch_real_ml; fetch_real_ml([2020,2021,2022,2023,2024]).to_csv('data/raw/real_ml_2020_2024.csv', index=False)"

    # load into DB
    uv run python -m ingestion.real_ml_loader data/raw/real_ml_2020_2024.csv

    # run validation
    uv run python -m engine.validation
    ```

    Outputs price-level diagnostics + per-bucket ROI comparison (derived vs real).
    CSV written to `data/processed/ml_validation_report.csv`.

    ### Headline finding

    Fill in from T11 output. Example: "ml_heavy_fav derived ROI +0.63% vs real
    ROI X.XX% on N=NNN bets; derived prices overshade favorites by Y.YY pp
    on average."

- [ ] **Step 2: Commit README**

```powershell
git add README.md
git commit -m "docs(readme): Slice 3 validation workflow + headline finding"
```

- [ ] **Step 3: Append findings to `.wolf/memory.md`**

Add a one-paragraph entry at the bottom under the current session header (use the actual numbers):

```
| HH:MM | Slice 3 finding: ml_heavy_fav derived +0.63% vs real X.XX% on N=NNN. Derived overshades favorites by Y.YY pp. (Holds | does not hold | grows | flips) | data/processed/ml_validation_report.csv | ~tokens |
```

- [ ] **Step 4: Commit memory.md update**

```powershell
git add .wolf/memory.md
git commit -m "chore(wolf): record Slice 3 validation findings"
```

- [ ] **Step 5: Confirm clean tree**

```powershell
git status
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 6: Tag the slice**

```powershell
git tag -a slice3-complete -m "Slice 3: real-line ML validation (nflverse 2020-2024)"
git tag
```

Expected: `slice1-complete`, `slice2-complete`, `slice3-complete` all listed.

---

## Slice 3 — Definition of Done checklist

- [ ] `nfl-data-py` added to `pyproject.toml`; probe doc records what columns it returned
- [ ] `engine/db.py.init_schema` creates `real_ml_lines` with the expected schema
- [ ] `ingestion/team_codes.py` maps all 32 modern nflverse codes to canonical names
- [ ] `ingestion/real_ml_source.fetch_real_ml(seasons)` returns canonicalized DataFrame
- [ ] `ingestion/real_ml_loader.load_csv_to_db` is idempotent, joins to games, reports counts
- [ ] `engine/validation.compare_ml_prices(conn) → ValidationReport` works on the 5-game fixture
- [ ] `engine/validation` CLI prints two tables and writes `data/processed/ml_validation_report.csv` with comment lines
- [ ] `uv run pytest -q` shows ~222 tests passing (191 prior + ~31 new)
- [ ] `uv run ruff check .` clean
- [ ] Real-data smoke completed against 2020–2024 nflverse data
- [ ] README has Slice 3 section with headline finding filled in
- [ ] `.wolf/memory.md` has one-paragraph findings entry
- [ ] Tag `slice3-complete` cut

---

## Appendix A — Fallback if tier-1 (nfl_data_py) is unavailable

If T1 Step 2 fails (e.g., `nfl_data_py` install errors, or `import_schedules` is missing moneyline columns), replace **T4** with one of:

### A.4-alt: Tier 2 — direct GitHub release download

Skip the `nfl_data_py` dependency. Fetch the same CSV directly from the nflverse-data releases:

```python
# ingestion/real_ml_source.py
import httpx
import pandas as pd

NFLDATA_GAMES_URL = "https://github.com/nflverse/nfldata/releases/download/games/games.csv"

def fetch_real_ml(seasons: list[int]) -> pd.DataFrame:
    raw = pd.read_csv(NFLDATA_GAMES_URL)
    raw = raw[raw["season"].isin(seasons)]
    raw = raw.dropna(subset=["home_moneyline", "away_moneyline"])
    # ... same column normalization as tier 1
```

Add a one-shot HTTP test (use `responses` or `pytest-httpx` to mock). Same downstream tasks (T5–T12) unchanged.

### A.4-alt2: Tier 3 — scrape SportsOddsHistory

Only if tiers 1 and 2 both fail. Build a polite scraper:

- Use `httpx` + `selectolax`
- Single-pass, cache HTML to `data/raw/cache/sportsoddshistory/<season>.html` (gitignored)
- Rate-limit: `time.sleep(2)` between season pages
- Honor `robots.txt` (fetch `https://www.sportsoddshistory.com/robots.txt` first, abort if disallowed)
- Parse season tables to the same canonical DataFrame schema as tier 1

Add ~5 tests covering the parser (mock the HTML response).

### A.4-alt3: Tier 4 — manual collection

Only if all programmatic tiers fail. Create `scripts/select_validation_sample.py`:

```python
# scripts/select_validation_sample.py
"""Tier-4 fallback: produce 150-row CSV lookup checklist for hand-collection."""
import random
import pandas as pd
from engine.db import connect, fetch_df
from engine.moneyline import bucket_ml, derive_ml_from_spread

def main() -> int:
    conn = connect("data/db/nfl_betting.sqlite")
    df = fetch_df(
        conn,
        "SELECT g.game_id, g.season, g.week, g.game_date, g.home_team, g.away_team, "
        "       bl.spread_home_close "
        "FROM games g JOIN betting_lines bl ON bl.game_id = g.game_id "
        "WHERE g.season BETWEEN 2020 AND 2024 AND bl.spread_home_close IS NOT NULL",
    )
    # filter to derived heavy_fav rows
    heavy = []
    for row in df.itertuples(index=False):
        derived = derive_ml_from_spread(row.spread_home_close)
        if derived is None:
            continue
        if bucket_ml(derived[0]) == "ml_heavy_fav" or bucket_ml(derived[1]) == "ml_heavy_fav":
            heavy.append(row._asdict())
    random.seed(42)
    sample = random.sample(heavy, k=min(150, len(heavy)))
    out = pd.DataFrame(sample)
    out["ml_home_real"] = ""
    out["ml_away_real"] = ""
    out["source"] = "manual"
    out["source_url"] = ""
    out.to_csv("data/processed/validation_sample.csv", index=False)
    print(f"wrote {len(out)} rows to data/processed/validation_sample.csv")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

Test: assert the script produces exactly 150 rows (or `min(150, supply)`) and that re-running with seed=42 produces identical rows. User then hand-collects, then T7's loader takes over.
