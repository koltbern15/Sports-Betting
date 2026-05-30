# NFL Betting Analytics — Slice 6: Opening-Line Ingestion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest free historical NFL opening lines (spread + total, moneyline if available) from SportsbookReviewsOnline (2007–2021) and Australia Sports Betting (2013–2024) into a new `opening_lines` table, then run a full data-quality audit (overlap agreement, closer sanity, coverage, outliers) with a written findings note.

**Architecture:** Additive, mirroring the existing `ingestion/` split. A verification probe (Task 1) gates the source-specific parser tasks. Deterministic foundation — schema, a shared `OpeningLineRecord` + normalization helpers, the loader, and the audit math — is built with full TDD and is independent of the parsers (parsers feed records; loader/audit are tested on synthetic records/data). The two source parsers (Tasks 6–7) are scaffolded here; their exact field extraction is finalized against the probe's saved fixtures during execution.

**Tech Stack:** Python 3.11, `sqlite3` (stdlib), `pandas`, `openpyxl` (xlsx, NEW dep), `lxml` (pandas `read_html`, NEW dep), `urllib` (stdlib, fetching), `pytest`, `uv`, `ruff`.

**Probe-gate note (read first):** Tasks 6 and 7 parse real external HTML/xlsx. You cannot write a correct parser without the real sample in front of you, and one source (aussportsbetting) was JS-gated during research so its exact columns and moneyline presence are UNCONFIRMED. Task 1 resolves this. When executing subagent-driven, run Task 1 first, then provide its findings + the saved fixtures to the Task 6/7 implementers. If the probe reveals a blocker (e.g. aussportsbetting requires a browser to download, or has no usable ML), STOP and surface it — do not guess.

---

## File structure

| File | Responsibility | Lifecycle |
|---|---|---|
| `docs/superpowers/notes/2026-05-29-opening-line-probe.md` | Probe findings (source structure, columns, ML verdict, date format, parse strategy) | NEW |
| `engine/db.py` | Add `opening_lines` table + index | MODIFY |
| `tests/test_db.py` | Tests for the new table | MODIFY |
| `ingestion/opening_line_common.py` | `OpeningLineRecord` + pure normalization helpers (sign, date→ISO, team) | NEW |
| `tests/test_opening_line_common.py` | Helper + record tests | NEW |
| `ingestion/opening_line_loader.py` | Join records to `games`, insert into `opening_lines`, count unmatched, canonical-opener precedence helper | NEW |
| `tests/test_opening_line_loader.py` | Loader tests vs in-memory DB | NEW |
| `engine/opener_audit.py` | Pure audit math (agreement %, close−open stats, outliers) | NEW |
| `tests/test_opener_audit.py` | Audit-math tests on synthetic data | NEW |
| `scripts/cross_check_openers.py` | Audit orchestration: read DB, run audit math, write findings note | NEW |
| `ingestion/opening_line_sbr.py` | Fetch + parse SBR HTML → `OpeningLineRecord`s | NEW (probe-gated) |
| `tests/test_opening_line_sbr.py` | SBR parser tests vs saved HTML fixture | NEW (probe-gated) |
| `ingestion/opening_line_aus.py` | Download + parse aussportsbetting xlsx → `OpeningLineRecord`s | NEW (probe-gated) |
| `tests/test_opening_line_aus.py` | aus parser tests vs saved xlsx fixture | NEW (probe-gated) |
| `docs/superpowers/notes/2026-05-29-opening-line-audit.md` | Audit findings (written by the cross-check run) | NEW |
| `pyproject.toml` | Add `openpyxl` + `lxml` | MODIFY |
| `tests/fixtures/` | Small saved SBR HTML + aus xlsx samples | NEW |
| `README.md` | Slice 6 workflow | MODIFY |

---

## Task 1: Verification probe (GATE)

This is a discovery task. Output is a findings note + saved raw samples, NOT production code. It gates Tasks 6–7.

**Files:**
- Modify: `pyproject.toml` (add deps)
- Create: `docs/superpowers/notes/2026-05-29-opening-line-probe.md`
- Create (raw, gitignored): `data/raw/sbr_2021.html`, `data/raw/aus_nfl.xlsx`

- [ ] **Step 1: Add dependencies**

Run: `uv add openpyxl lxml`
Expected: `pyproject.toml` gains `openpyxl` and `lxml`; `uv.lock` updates; exit 0.

- [ ] **Step 2: Fetch and save an SBR season page**

Use Python (stdlib urllib) to download one season page and save it:
```python
import urllib.request
url = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl-odds-2021-22/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read()
open("data/raw/sbr_2021.html", "wb").write(html)
print(len(html))
```
Expected: a ~100–120 KB HTML file saved. If it 403s or returns a JS challenge, record that and try the `.../scoresoddsarchives/nfl/nfloddsarchives.htm` index to confirm the correct current URL pattern.

- [ ] **Step 3: Inspect SBR structure**

Load with pandas and inspect:
```python
import pandas as pd
tables = pd.read_html("data/raw/sbr_2021.html")
print(len(tables), [t.shape for t in tables])
print(tables[0].head(6).to_string())
print(list(tables[0].columns))
```
Record in the probe note: how many tables, the column headers, the two-rows-per-game layout, how the `Open`/`Close` columns interleave spread and total, the `Date`/`Rot`/`VH`/`Team`/`ML` columns, the date format (e.g. `911` = Sep 11), and how to pair the two team rows into one game. Note any "pk" (pickem) handling.

- [ ] **Step 4: Fetch and inspect the aussportsbetting xlsx**

Find the current xlsx download URL from `https://www.aussportsbetting.com/data/historical-nfl-results-and-odds-data/` (the link is typically a direct `.xlsx`). Download via urllib (same User-Agent pattern) to `data/raw/aus_nfl.xlsx`. Then:
```python
import pandas as pd
df = pd.read_excel("data/raw/aus_nfl.xlsx")
print(df.shape)
print(list(df.columns))
print(df.head(5).to_string())
```
Record in the probe note: exact column names, the date column + format, the spread/total/moneyline columns, **whether opening odds columns exist** (look for "Open" in any spread/total/H2H column name), whether odds are decimal or American, and the sign convention for the spread. **This is the decisive ML check.**

- [ ] **Step 5: Decide and document**

Write `docs/superpowers/notes/2026-05-29-opening-line-probe.md` recording, for BOTH sources: the verified column layout, the date format, the spread sign convention, whether opening lines (and opening ML) are present, the earliest/latest season, and the concrete parse strategy. State the ML verdict explicitly: **ML IN** (aus has clean opening ML) or **ML DEFERRED**. If either source needs a browser (Cloudflare/JS), record that as a blocker and stop for re-scoping.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock docs/superpowers/notes/2026-05-29-opening-line-probe.md
git commit -m "chore(slice6): opening-line source probe + openpyxl/lxml deps

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
(Do NOT commit `data/raw/*` — it is gitignored.)

---

## Task 2: `opening_lines` schema

**Files:**
- Modify: `engine/db.py` (append to `_SCHEMA_SQL`, after the `real_ml_lines` block ~line 66)
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py` (the file already imports `connect`, `init_schema`; follow its existing style):
```python
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
```
Ensure `import pytest` is present at the top of `tests/test_db.py` (add if missing).

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_db.py -q`
Expected: FAIL — `no such table: opening_lines`.

- [ ] **Step 3: Implement the schema**

In `engine/db.py`, inside the `_SCHEMA_SQL` string, after the `idx_real_ml_lines_game` index line and before the closing `"""`, add:
```sql

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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_db.py -q`
Expected: PASS. Then full suite `uv run pytest -q` — green.

- [ ] **Step 5: Commit**

```bash
git add engine/db.py tests/test_db.py
git commit -m "feat(db): opening_lines table (game_id, source composite key)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `OpeningLineRecord` + normalization helpers

**Files:**
- Create: `ingestion/opening_line_common.py`
- Test: `tests/test_opening_line_common.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_opening_line_common.py`:
```python
"""Tests for ingestion.opening_line_common — pure record + normalization helpers."""

from __future__ import annotations

import pytest

from ingestion.opening_line_common import (
    OpeningLineRecord,
    canonical_team,
    decimal_to_american,
    normalize_spread_sign,
    to_iso_date,
)


def test_canonical_team_passthrough_known():
    assert canonical_team("Dallas Cowboys") == "Dallas Cowboys"


def test_canonical_team_normalizes_relocation():
    assert canonical_team("Oakland Raiders") == "Las Vegas Raiders"


def test_canonical_team_unknown_raises():
    with pytest.raises(KeyError):
        canonical_team("Springfield Isotopes")


def test_to_iso_date_from_mmdd_fall_game():
    # SBR-style MMDD within a season: Sep 13, 2015 season
    assert to_iso_date_mmdd(913, 2015) == "2015-09-13"


def test_to_iso_date_from_mmdd_january_rolls_year():
    # A January game in the 2015 season is calendar year 2016
    assert to_iso_date_mmdd(103, 2015) == "2016-01-03"


def test_to_iso_date_passthrough_datetime():
    import datetime
    assert to_iso_date(datetime.date(2015, 9, 13)) == "2015-09-13"


def test_normalize_spread_sign_home_favored_negative():
    # If source gives the favorite's line as a positive magnitude and a flag,
    # home-favored must come out negative.
    assert normalize_spread_sign(3.0, home_is_favorite=True) == -3.0
    assert normalize_spread_sign(3.0, home_is_favorite=False) == 3.0


def test_decimal_to_american_favorite():
    # 1.50 decimal -> -200 American
    assert decimal_to_american(1.50) == -200


def test_decimal_to_american_underdog():
    # 2.50 decimal -> +150 American
    assert decimal_to_american(2.50) == 150


def test_decimal_to_american_none_passthrough():
    assert decimal_to_american(None) is None


def test_record_is_frozen():
    r = OpeningLineRecord(
        season=2015, game_date="2015-09-13", home_team="Dallas Cowboys",
        away_team="New York Giants", open_spread_home=-3.0, open_total=47.0,
        open_ml_home=None, open_ml_away=None, source="sbr",
        source_url="http://example",
    )
    with pytest.raises(Exception):
        r.season = 2016  # frozen
```
Note: the test imports `to_iso_date` and also calls `to_iso_date_mmdd` — add `to_iso_date_mmdd` to the import list as well.

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_opening_line_common.py -q`
Expected: FAIL / ImportError.

- [ ] **Step 3: Implement**

Create `ingestion/opening_line_common.py`:
```python
"""Shared types + pure normalization helpers for opening-line ingestion.

Both source parsers (SBR, aussportsbetting) emit OpeningLineRecord and reuse
these helpers so the loader is source-agnostic.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from ingestion.team_names import canonicalize_team_name


@dataclass(frozen=True)
class OpeningLineRecord:
    season: int
    game_date: str  # ISO yyyy-mm-dd, matches games.game_date
    home_team: str  # canonical full name
    away_team: str
    open_spread_home: float | None  # home-perspective, negative = home favored
    open_total: float | None
    open_ml_home: int | None  # American odds; None if source lacks ML
    open_ml_away: int | None
    source: str  # 'sbr' | 'aus'
    source_url: str


def canonical_team(name: str) -> str:
    """Normalize a team name to canonical full form. Raises KeyError if unknown."""
    return canonicalize_team_name(name.strip())


def to_iso_date(d: datetime.date | datetime.datetime) -> str:
    """Format a date/datetime as ISO yyyy-mm-dd."""
    if isinstance(d, datetime.datetime):
        d = d.date()
    return d.isoformat()


def to_iso_date_mmdd(mmdd: int, season: int) -> str:
    """Convert an SBR-style MMDD integer within an NFL season to ISO yyyy-mm-dd.

    NFL seasons span Sep–Feb. Months >= 8 belong to the season's calendar year;
    months <= 7 (Jan/Feb playoffs) belong to season + 1.
    """
    month = mmdd // 100
    day = mmdd % 100
    year = season if month >= 8 else season + 1
    return datetime.date(year, month, day).isoformat()


def normalize_spread_sign(magnitude: float, *, home_is_favorite: bool) -> float:
    """Return the home-perspective spread: negative when the home team is favored."""
    m = abs(magnitude)
    return -m if home_is_favorite else m


def decimal_to_american(decimal_odds: float | None) -> int | None:
    """Convert decimal odds to American odds (int), or None if input is None."""
    if decimal_odds is None:
        return None
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal odds must be > 1.0, got {decimal_odds}")
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1.0) * 100)
    return -round(100.0 / (decimal_odds - 1.0))
```
Verify `canonicalize_team_name` is the correct exported name in `ingestion/team_names.py` (it is, per the real-ML loader / cerebrum notes). If the actual export differs, adjust the import.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_opening_line_common.py -q` then `uv run pytest -q`.
Expected: PASS, full suite green.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check ingestion/opening_line_common.py tests/test_opening_line_common.py
git add ingestion/opening_line_common.py tests/test_opening_line_common.py
git commit -m "feat(ingestion): OpeningLineRecord + normalization helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Loader

**Files:**
- Create: `ingestion/opening_line_loader.py`
- Test: `tests/test_opening_line_loader.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_opening_line_loader.py`:
```python
"""Tests for ingestion.opening_line_loader — join + insert vs in-memory DB."""

from __future__ import annotations

from engine.db import connect, init_schema
from ingestion.opening_line_common import OpeningLineRecord
from ingestion.opening_line_loader import (
    canonical_opener_source,
    load_records,
)


def _seed_game(conn, game_id, season, week, date, home, away):
    conn.execute(
        "INSERT INTO games (game_id, season, week, game_date, home_team, away_team)"
        " VALUES (?,?,?,?,?,?)",
        (game_id, season, week, date, home, away),
    )


def _rec(season, date, home, away, source, spread=-3.0, total=47.0):
    return OpeningLineRecord(
        season=season, game_date=date, home_team=home, away_team=away,
        open_spread_home=spread, open_total=total, open_ml_home=None,
        open_ml_away=None, source=source, source_url="http://x",
    )


def test_load_matches_on_season_home_away():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    report = load_records(conn, [_rec(2015, "2015-09-13", "Dallas Cowboys", "New York Giants", "sbr")])
    assert report.inserted == 1
    assert report.unmatched == 0
    row = conn.execute(
        "SELECT open_spread_home, source FROM opening_lines WHERE game_id='g1'"
    ).fetchone()
    assert row[0] == -3.0 and row[1] == "sbr"
    conn.close()


def test_two_sources_coexist():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    load_records(conn, [
        _rec(2015, "2015-09-13", "Dallas Cowboys", "New York Giants", "sbr", spread=-3.0),
        _rec(2015, "2015-09-13", "Dallas Cowboys", "New York Giants", "aus", spread=-3.5),
    ])
    n = conn.execute("SELECT COUNT(*) FROM opening_lines WHERE game_id='g1'").fetchone()[0]
    assert n == 2
    conn.close()


def test_unmatched_record_is_counted_not_inserted():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    report = load_records(conn, [_rec(2015, "2015-09-20", "Green Bay Packers", "Chicago Bears", "sbr")])
    assert report.inserted == 0
    assert report.unmatched == 1
    conn.close()


def test_repeat_matchup_disambiguated_by_date():
    conn = connect(":memory:")
    init_schema(conn)
    # Same teams play twice (different home/away handled separately; here same home twice rare,
    # but a divisional season could list the pairing once — we still disambiguate by date).
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    _seed_game(conn, "g2", 2015, 12, "2015-12-06", "Dallas Cowboys", "New York Giants")
    report = load_records(conn, [_rec(2015, "2015-12-06", "Dallas Cowboys", "New York Giants", "sbr")])
    assert report.inserted == 1
    gid = conn.execute("SELECT game_id FROM opening_lines").fetchone()[0]
    assert gid == "g2"
    conn.close()


def test_idempotent_reload():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_game(conn, "g1", 2015, 1, "2015-09-13", "Dallas Cowboys", "New York Giants")
    rec = _rec(2015, "2015-09-13", "Dallas Cowboys", "New York Giants", "sbr")
    load_records(conn, [rec])
    load_records(conn, [rec])
    n = conn.execute("SELECT COUNT(*) FROM opening_lines").fetchone()[0]
    assert n == 1
    conn.close()


def test_canonical_opener_source_precedence():
    assert canonical_opener_source(2010) == "sbr"
    assert canonical_opener_source(2018) == "aus"
    assert canonical_opener_source(2023) == "aus"
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_opening_line_loader.py -q`
Expected: FAIL / ImportError.

- [ ] **Step 3: Implement**

Create `ingestion/opening_line_loader.py`:
```python
"""Load OpeningLineRecords into the opening_lines table.

Joins each record to games on (season, home_team, away_team), disambiguating the
rare repeat matchup by game_date. Stores one row per (game_id, source) — both
sources coexist for cross-validation. Idempotent via INSERT OR REPLACE.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ingestion.opening_line_common import OpeningLineRecord


@dataclass(frozen=True)
class OpeningLoadReport:
    inserted: int
    unmatched: int
    errors: list[str] = field(default_factory=list)


def _find_game_id(conn: sqlite3.Connection, rec: OpeningLineRecord) -> str | None:
    """Return the matching game_id, or None. Disambiguate repeats by game_date."""
    rows = conn.execute(
        "SELECT game_id, game_date FROM games"
        " WHERE season=? AND home_team=? AND away_team=?",
        (rec.season, rec.home_team, rec.away_team),
    ).fetchall()
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0][0]
    for game_id, game_date in rows:
        if game_date == rec.game_date:
            return game_id
    return None


def load_records(
    conn: sqlite3.Connection, records: list[OpeningLineRecord]
) -> OpeningLoadReport:
    """Insert records into opening_lines. Idempotent. Unmatched are counted, not inserted."""
    inserted = 0
    unmatched = 0
    errors: list[str] = []
    now_iso = datetime.now(UTC).isoformat(timespec="seconds")

    for rec in records:
        game_id = _find_game_id(conn, rec)
        if game_id is None:
            unmatched += 1
            errors.append(
                f"no game for {rec.season} {rec.away_team} @ {rec.home_team} ({rec.game_date})"
            )
            continue
        conn.execute(
            "INSERT OR REPLACE INTO opening_lines"
            " (game_id, source, open_spread_home, open_total, open_ml_home,"
            "  open_ml_away, source_url, collected_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                game_id, rec.source, rec.open_spread_home, rec.open_total,
                rec.open_ml_home, rec.open_ml_away, rec.source_url, now_iso,
            ),
        )
        inserted += 1
    conn.commit()
    return OpeningLoadReport(inserted=inserted, unmatched=unmatched, errors=errors)


def canonical_opener_source(season: int) -> str:
    """Documented precedence for the canonical opener per season.

    2007-2012: only SBR has data. 2013+: prefer aussportsbetting (still maintained,
    the only ML source). In the 2013-2021 overlap SBR is retained as the cross-check
    counterpart but 'aus' is canonical. Tunable after the audit (see findings note).
    """
    return "sbr" if season <= 2012 else "aus"
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_opening_line_loader.py -q` then `uv run pytest -q`.
Expected: PASS, full suite green.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check ingestion/opening_line_loader.py tests/test_opening_line_loader.py
git add ingestion/opening_line_loader.py tests/test_opening_line_loader.py
git commit -m "feat(ingestion): opening_lines loader + canonical-source precedence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Audit math + cross-check script

**Files:**
- Create: `engine/opener_audit.py`
- Test: `tests/test_opener_audit.py`
- Create: `scripts/cross_check_openers.py`

- [ ] **Step 1: Write the failing tests (pure audit math)**

Create `tests/test_opener_audit.py`:
```python
"""Tests for engine.opener_audit — pure audit math on synthetic data."""

from __future__ import annotations

import pytest

from engine.opener_audit import (
    agreement_rate,
    movement_stats,
    outliers,
)


def test_agreement_rate_within_tolerance():
    a = [-3.0, -7.0, 2.5, 0.0]
    b = [-3.0, -7.5, 2.5, 0.5]
    # |diff|: 0, 0.5, 0, 0.5 — all within 0.5 tolerance
    assert agreement_rate(a, b, tol=0.5) == pytest.approx(1.0)
    # within 0.4: only the two exact matches agree → 0.5
    assert agreement_rate(a, b, tol=0.4) == pytest.approx(0.5)


def test_agreement_rate_skips_none_pairs():
    a = [-3.0, None, 2.0]
    b = [-3.0, 5.0, None]
    # only the first pair is comparable, and it agrees → 1.0
    assert agreement_rate(a, b, tol=0.5) == pytest.approx(1.0)


def test_agreement_rate_no_comparable_pairs_is_nan():
    import math
    assert math.isnan(agreement_rate([None], [None], tol=0.5))


def test_movement_stats_close_minus_open():
    opens = [-3.0, -7.0]
    closes = [-3.5, -6.0]
    # diffs (close - open): -0.5, +1.0 → mean 0.25
    stats = movement_stats(opens, closes)
    assert stats["mean"] == pytest.approx(0.25)
    assert stats["n"] == 2


def test_outliers_flags_large_abs_diff():
    opens = [-3.0, -3.0, -3.0]
    closes = [-3.5, -10.0, -3.0]
    # |close-open|: 0.5, 7.0, 0.0 — only index 1 exceeds threshold 3.0
    flagged = outliers(opens, closes, threshold=3.0)
    assert flagged == [1]
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_opener_audit.py -q` → FAIL/ImportError.

- [ ] **Step 3: Implement audit math**

Create `engine/opener_audit.py`:
```python
"""Pure audit math for opening-line data quality. No I/O."""

from __future__ import annotations

import math
from statistics import mean, pstdev


def agreement_rate(a: list[float | None], b: list[float | None], *, tol: float) -> float:
    """Share of comparable (both non-None) pairs whose |a-b| <= tol. NaN if none comparable."""
    pairs = [(x, y) for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    if not pairs:
        return math.nan
    agree = sum(1 for x, y in pairs if abs(x - y) <= tol)
    return agree / len(pairs)


def movement_stats(opens: list[float | None], closes: list[float | None]) -> dict:
    """Stats on (close - open) over comparable pairs."""
    diffs = [
        c - o
        for o, c in zip(opens, closes, strict=True)
        if o is not None and c is not None
    ]
    if not diffs:
        return {"n": 0, "mean": math.nan, "stdev": math.nan}
    return {"n": len(diffs), "mean": mean(diffs), "stdev": pstdev(diffs) if len(diffs) > 1 else 0.0}


def outliers(
    opens: list[float | None], closes: list[float | None], *, threshold: float
) -> list[int]:
    """Indices where |close - open| exceeds threshold (both non-None)."""
    out = []
    for i, (o, c) in enumerate(zip(opens, closes, strict=True)):
        if o is not None and c is not None and abs(c - o) > threshold:
            out.append(i)
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_opener_audit.py -q` then `uv run pytest -q` → PASS, green.

- [ ] **Step 5: Implement the audit orchestration script**

Create `scripts/cross_check_openers.py`. This is thin orchestration over `opener_audit` math + DB reads; it is exercised manually (no unit test — like `scripts/cross_check_ats_totals.py`). It must:
1. Connect to `data/db/nfl_betting.sqlite`.
2. **Coverage:** per source, per season, count `opening_lines` rows joined to `games`; print a table.
3. **Overlap agreement (2013–2021):** for games with BOTH `sbr` and `aus` rows, build aligned lists of `open_spread_home` and of `open_total`, call `agreement_rate(..., tol=0.5)` and `tol=1.0`; print both; print the worst 10 disagreements per market.
4. **Closer sanity:** join `opening_lines` (canonical source via `canonical_opener_source`) to `betting_lines`; build `opens`/`closes` lists for spread and total; print `movement_stats`; print games flagged by `outliers(threshold=7.0)` for spread.
5. **ML status:** count non-null `open_ml_home` rows; print.
6. Write all of the above to `docs/superpowers/notes/2026-05-29-opening-line-audit.md` (build a markdown string, `Path.write_text`, utf-8).
Use `pandas.read_sql_query` for the joins (the codebase already uses pandas for DB reads in `engine/moneyline.py`). Keep functions small; put the SQL inline.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check engine/opener_audit.py tests/test_opener_audit.py scripts/cross_check_openers.py
git add engine/opener_audit.py tests/test_opener_audit.py scripts/cross_check_openers.py
git commit -m "feat(slice6): opener audit math + cross-check script

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: SBR parser (PROBE-GATED)

**Prerequisite:** Task 1 complete; `data/raw/sbr_2021.html` saved; the probe note documents the SBR table layout, the spread/total interleave, the date (MMDD) format, and the sign convention. The controller provides those findings to this task.

**Files:**
- Create: `ingestion/opening_line_sbr.py`
- Create: `tests/fixtures/sbr_sample.html` (a SMALL excerpt of `data/raw/sbr_2021.html` — a few complete games including a pickem "pk" and one deliberately broken row)
- Test: `tests/test_opening_line_sbr.py`

- [ ] **Step 1: Build the fixture**

From the saved `data/raw/sbr_2021.html`, extract a minimal valid HTML fragment containing the odds `<table>` with ~3–4 games (6–8 team rows), keeping the real header row. Save as `tests/fixtures/sbr_sample.html`. Hand-record the expected `OpeningLineRecord` values for those games (read them off the real table) — these are the golden values for the test.

- [ ] **Step 2: Write the failing test**

Create `tests/test_opening_line_sbr.py` asserting that `parse_sbr_html(html, season=2021)` returns the hand-verified `OpeningLineRecord`s for the fixture games: correct `home_team`/`away_team` (canonical), correct `open_spread_home` (home-perspective sign), correct `open_total`, correct `game_date` (ISO from MMDD), `source == "sbr"`, and that the deliberately broken row is skipped (so the count is the number of valid games). Include a pickem game asserting `open_spread_home == 0.0`. Use the exact golden values you recorded in Step 1. Read the fixture via `Path(__file__).parent / "fixtures" / "sbr_sample.html"`.

- [ ] **Step 3: Run to verify fail** → ImportError/FAIL.

- [ ] **Step 4: Implement the parser**

Create `ingestion/opening_line_sbr.py` with this STRUCTURE (finalize the field-extraction against the probe note + fixture):
```python
"""Parse SportsbookReviewsOnline NFL odds archive HTML into OpeningLineRecords.

SBR lists two rows per game (away then home). The Open/Close columns interleave
the side spread and the game total. This module pairs the rows, untangles
spread vs total, and emits home-perspective records. See the probe note
docs/superpowers/notes/2026-05-29-opening-line-probe.md for the verified layout.
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import pandas as pd

from ingestion.opening_line_common import (
    OpeningLineRecord,
    canonical_team,
    normalize_spread_sign,
    to_iso_date_mmdd,
)

_BASE_URL = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl-odds-{a}-{b}/"


def parse_sbr_html(html: str | bytes, season: int) -> list[OpeningLineRecord]:
    """Parse one SBR season page into OpeningLineRecords. Malformed games skipped+counted."""
    tables = pd.read_html(io.StringIO(html) if isinstance(html, str) else io.BytesIO(html))
    df = _select_odds_table(tables)
    records: list[OpeningLineRecord] = []
    # Pair consecutive rows (away, home). For each pair:
    #   - parse Date (MMDD int) -> to_iso_date_mmdd(mmdd, season)
    #   - canonical_team(away_name), canonical_team(home_name)
    #   - untangle Open column: the favorite's row carries the side spread (or 'pk'->0.0);
    #     the other row carries the game total. Determine home_is_favorite from sign/VH.
    #   - open_spread_home = normalize_spread_sign(magnitude, home_is_favorite=...)
    #   - wrap each pair in try/except; on failure, increment a skip counter (log) and continue.
    # FINALIZE the exact column names/indices against tests/fixtures/sbr_sample.html.
    ...
    return records


def _select_odds_table(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Pick the games table from pd.read_html output (the one with the Date/Team/Open cols)."""
    ...


def fetch_season(season: int) -> str:
    """Download a season page (cached to data/raw/). season=2021 -> the 2021-22 page."""
    url = _BASE_URL.format(a=season, b=str(season + 1)[-2:])
    cache = Path(f"data/raw/sbr_{season}.html")
    if cache.exists():
        return cache.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(html, encoding="utf-8")
    return html
```
Replace each `...` with concrete logic derived from the probe fixture. The pairing/untangle is the crux; the probe note describes the exact interleave. Keep `parse_sbr_html` pure (takes HTML, returns records) so the test never hits the network; `fetch_season` is the I/O boundary.

- [ ] **Step 5: Run to verify pass** → `uv run pytest tests/test_opening_line_sbr.py -q` PASS; full suite green; `uv run ruff check` clean.

- [ ] **Step 6: Commit**

```bash
git add ingestion/opening_line_sbr.py tests/test_opening_line_sbr.py tests/fixtures/sbr_sample.html
git commit -m "feat(ingestion): SBR opening-line HTML parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: aussportsbetting parser (PROBE-GATED)

**Prerequisite:** Task 1 complete; `data/raw/aus_nfl.xlsx` saved; the probe note documents the exact columns, date format, decimal-vs-American odds, spread sign, and the ML verdict. Controller provides those to this task. **If the probe set ML DEFERRED, leave `open_ml_*` as None here.**

**Files:**
- Create: `ingestion/opening_line_aus.py`
- Create: `tests/fixtures/aus_sample.xlsx` (a SMALL xlsx with the real columns + ~3–4 rows)
- Test: `tests/test_opening_line_aus.py`

- [ ] **Step 1: Build the fixture**

Create `tests/fixtures/aus_sample.xlsx` containing the REAL column headers (from the probe) and ~3–4 hand-built rows with known opening spread/total (and ML if present). Use `pandas.DataFrame(...).to_excel(path, index=False)`. Record the expected `OpeningLineRecord`s as golden values.

- [ ] **Step 2: Write the failing test**

Create `tests/test_opening_line_aus.py` asserting `parse_aus_xlsx(path)` returns the golden `OpeningLineRecord`s: canonical teams, `open_spread_home` (home-perspective sign), `open_total`, `game_date` ISO, and — if ML present — `open_ml_home`/`open_ml_away` converted decimal→American; else those are None. `source == "aus"`. Assert a row missing an opening spread yields `open_spread_home=None` (not a crash).

- [ ] **Step 3: Run to verify fail** → ImportError/FAIL.

- [ ] **Step 4: Implement**

Create `ingestion/opening_line_aus.py` with this STRUCTURE (finalize columns against the probe + fixture):
```python
"""Parse the Australia Sports Betting NFL xlsx into OpeningLineRecords.

Opening odds present from 2013+. Odds may be decimal (converted to American).
See docs/superpowers/notes/2026-05-29-opening-line-probe.md for verified columns.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pandas as pd

from ingestion.opening_line_common import (
    OpeningLineRecord,
    canonical_team,
    decimal_to_american,
    normalize_spread_sign,
    to_iso_date,
)

_XLSX_URL = "<confirm from probe>"  # the direct .xlsx link from the data page


def parse_aus_xlsx(path: str | Path) -> list[OpeningLineRecord]:
    """Parse the aussportsbetting xlsx into OpeningLineRecords (opening lines only)."""
    df = pd.read_excel(path)
    records: list[OpeningLineRecord] = []
    for row in df.itertuples(index=False):
        # FINALIZE against probe columns:
        #   - season from the date (NFL season = year if month>=8 else year-1)
        #   - game_date = to_iso_date(<date column>)
        #   - canonical_team(home), canonical_team(away)
        #   - open_spread_home = normalize_spread_sign(<open line>, home_is_favorite=<sign>)
        #   - open_total = <open total column> or None
        #   - open_ml_* = decimal_to_american(<open H2H column>) if ML present else None
        #   - wrap per-row in try/except; on a bad row, skip+count.
        ...
    return records


def download_xlsx() -> Path:
    """Download the xlsx to data/raw/aus_nfl.xlsx (cached)."""
    cache = Path("data/raw/aus_nfl.xlsx")
    if cache.exists():
        return cache
    req = urllib.request.Request(_XLSX_URL, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=60).read()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    return cache
```
Keep `parse_aus_xlsx` pure (reads a file path, no network). `download_xlsx` is the I/O boundary. If the probe found the download is Cloudflare-gated, record that the xlsx must be fetched manually in a browser into `data/raw/` and `download_xlsx` should raise a clear instruction if the file is absent.

- [ ] **Step 5: Run to verify pass** → PASS; full suite green; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add ingestion/opening_line_aus.py tests/test_opening_line_aus.py tests/fixtures/aus_sample.xlsx
git commit -m "feat(ingestion): aussportsbetting opening-line xlsx parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: End-to-end run, audit note, docs, bookkeeping

**Files:**
- Create: `docs/superpowers/notes/2026-05-29-opening-line-audit.md` (written by the script run)
- Modify: `README.md`, `.wolf/anatomy.md`, `.wolf/memory.md`, `.wolf/cerebrum.md`

- [ ] **Step 1: Load both sources into the DB (real network)**

Ensure `data/db/nfl_betting.sqlite` exists (from prior slices). Write a tiny throwaway driver (or use `python -c`) that: for each SBR season 2007–2021, `fetch_season(s)` then `parse_sbr_html(...)` then `load_records(conn, ...)`; then `parse_aus_xlsx(download_xlsx())` then `load_records(...)`. Print the cumulative `OpeningLoadReport` counts. Confirm `opening_lines` is populated:
```bash
uv run python -c "from engine.db import connect; c=connect('data/db/nfl_betting.sqlite'); print(c.execute('SELECT source, COUNT(*) FROM opening_lines GROUP BY source').fetchall())"
```
Expected: non-trivial counts for 'sbr' and 'aus'. If a season page or the xlsx fails to fetch, record it and continue with the rest; note gaps in the findings.

- [ ] **Step 2: Run the audit**

Run: `uv run python scripts/cross_check_openers.py`
Expected: prints coverage / overlap agreement / closer sanity / ML status, and writes `docs/superpowers/notes/2026-05-29-opening-line-audit.md`. Read the note; sanity-check the numbers (overlap agreement should be high if both sources are real; movement mean small).

- [ ] **Step 3: Update README**

Add a "## Slice 6 — Opening-line ingestion" section: what it does, the two sources + windows, the workflow commands (probe note ref, the load driver, `python scripts/cross_check_openers.py`), the `opening_lines` schema, and a one-line headline from the audit note. Add a Scope bullet: "**Slice 6 (complete):** historical opening-line ingestion (SBR 2007–2021 + aussportsbetting 2013–2024) into `opening_lines`, with a full data-quality audit. Foundation for CLV (Slice 7)."

- [ ] **Step 4: OpenWolf bookkeeping**

- `.wolf/anatomy.md`: add entries for the new modules/scripts/tests (or confirm the hook added them).
- `.wolf/memory.md`: append one Slice 6 summary line (re-read top + retry once if the hook touched it).
- `.wolf/cerebrum.md`: Decision Log entry (2026-05-29): "Slice 6 ingested free historical opening lines (SBR + aussportsbetting) into opening_lines; probe-first; <ML verdict>; CLV deferred to Slice 7."

- [ ] **Step 5: Final verification + commit**

```bash
uv run pytest -q
uv run ruff check .
git add README.md .wolf/anatomy.md .wolf/memory.md .wolf/cerebrum.md docs/superpowers/notes/2026-05-29-opening-line-audit.md
git commit -m "docs(slice6): opening-line audit findings + README + bookkeeping

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage:**
- Probe-first → Task 1. ✓
- `opening_lines` schema (composite key, nullable ML) → Task 2. ✓
- `OpeningLineRecord` + sign/date/team normalization → Task 3. ✓
- Loader: join on (season,home,away)+date, both sources coexist, unmatched counted, precedence helper → Task 4. ✓
- Full audit (coverage, overlap agreement, closer sanity, outliers, ML status) + findings note → Task 5 (math + script) + Task 8 (run). ✓
- SBR parser + aus parser, fixture-tested → Tasks 6, 7. ✓
- New deps openpyxl + lxml → Task 1 Step 1. ✓
- Markets: spread+total committed, ML probe-gated (nullable columns, parser leaves None if deferred) → Tasks 2/7. ✓
- README + bookkeeping → Task 8. ✓
- Out of scope (no CLV) → no task computes CLV. ✓

**Placeholder scan:** The `...` blocks in Tasks 6–7 are the deliberate, spec-acknowledged probe-gated extraction points (you cannot parse real HTML/xlsx blind). Every OTHER task has complete code. The probe-gated tasks carry full module scaffolding, signatures, helper wiring, error-handling contract, and golden-value test method — only the exact column mapping is filled from the saved fixture. This is the one honest non-determinism, flagged in the header and per-task.

**Type consistency:** `OpeningLineRecord` fields are identical across `opening_line_common.py` (Task 3), the loader (Task 4), and both parsers (Tasks 6–7). Function names consistent: `canonical_team`, `to_iso_date`, `to_iso_date_mmdd`, `normalize_spread_sign`, `decimal_to_american` (Task 3) used by Tasks 6–7; `load_records` / `canonical_opener_source` (Task 4); `agreement_rate` / `movement_stats` / `outliers` (Task 5). Source strings `'sbr'`/`'aus'` match the schema CHECK (Task 2). ✓

**Note on probe-gated tasks:** if Task 1 reports a blocker (browser-gated download, no usable ML, or a structurally different layout), pause and revise Tasks 6–7 with the controller before implementing — do not force the scaffolding to fit data it wasn't written for.
