# NFL Betting Analytics — Slice 8: Live "This Week" Odds Board — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull current NFL odds from The Odds API, store weekly snapshots, and present a refined-dark Streamlit "This Week" board showing the best available price per side (line shopping), live line movement, and labeled-uncertified historical context — framed as context + best price, never certified picks.

**Architecture:** Vertical slice. Pure, testable data layers (`ingestion/live_odds.py` parse + consensus + best-line; `ingestion/live_odds_store.py` snapshot persistence; `engine/this_week.py` board builder) under a thin Streamlit UI (`app/`). Reuses `ingestion.team_names` for normalization and `engine.ats`/`engine.totals` bucketers + the historical bucket CSVs for context. Odds fetch via stdlib `urllib` (no `requests`).

**Tech Stack:** Python 3.11, `sqlite3`, `pandas`, `streamlit` (NEW), `altair` (NEW), `urllib` (stdlib), `pytest`, `uv`, `ruff`.

**Probe-style note:** The Odds API schema is well-documented and the parse is built against a committed sample JSON fixture (Task 2), so no live network is needed to build/test. A real pull with the user's key happens only in Task 6. The user supplies `ODDS_API_KEY` themselves (never in source/transcript).

**Reused signatures (verified):**
- `ingestion.team_names.canonicalize_team_name(name) -> str` (raises KeyError unknown).
- `engine.ats.bucket_spread(spread_home_close) -> str|None`; `engine.totals.bucket_total(total_line) -> str|None`.
- Historical CSVs `data/processed/{ats_by_bucket,totals_by_bucket}.csv` — columns incl. `bucket, n, win_rate, ci_low, ci_high` (1 leading `#` comment line).
- `engine.db.connect(path)`, `init_schema(conn)`.

**The Odds API endpoint:** `GET https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?apiKey=KEY&regions=us&markets=spreads,totals,h2h&oddsFormat=american`. Returns a JSON list of events; each event has `id, commence_time, home_team, away_team, bookmakers[]`; each bookmaker has `key, title, markets[]`; each market has `key (spreads|totals|h2h), outcomes[]` with `name, price` (+`point` for spreads/totals).

---

## File structure

| File | Responsibility | Lifecycle |
|---|---|---|
| `engine/db.py` | Add `live_odds_snapshots` table | MODIFY |
| `tests/test_db.py` | Table test | MODIFY |
| `ingestion/live_odds.py` | Env key resolution; parse API JSON → `GameOdds` (consensus + best-line per side); thin `fetch` boundary | NEW |
| `tests/test_live_odds.py` | Parse/consensus/best-line tests vs sample fixture | NEW |
| `tests/fixtures/odds_api_sample.json` | Committed small sample payload | NEW |
| `ingestion/live_odds_store.py` | Store a snapshot; read opener (earliest) / current (latest) consensus per game | NEW |
| `tests/test_live_odds_store.py` | Store/read tests vs in-memory DB | NEW |
| `engine/this_week.py` | Board builder → `ThisWeekGame` (current, best price, movement, historical context, biggest movers) | NEW |
| `tests/test_this_week.py` | Builder tests on synthetic data | NEW |
| `app/__init__.py`, `app/theme.py`, `app/this_week_view.py`, `app/main.py` | Refined-dark Streamlit board (thin over the tested builder) | NEW |
| `tests/test_app_smoke.py` | Streamlit `AppTest` smoke test | NEW |
| `.streamlit/config.toml` | Refined-dark theme | NEW |
| `.env.example` | Documents `ODDS_API_KEY` | NEW |
| `.gitignore` | Add `.env`, `.streamlit/secrets.toml` | MODIFY |
| `pyproject.toml` | Add `streamlit`, `altair` | MODIFY |
| `README.md` | Slice 8 section | MODIFY |

---

## Task 1: `live_odds_snapshots` schema

**Files:** Modify `engine/db.py` (append to `_SCHEMA_SQL` before the closing `"""`); test `tests/test_db.py`.

- [ ] **Step 1: Write the failing test.** Append to `tests/test_db.py`:
```python
def test_init_schema_creates_live_odds_snapshots():
    conn = connect(":memory:")
    init_schema(conn)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='live_odds_snapshots'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_live_odds_snapshots_accepts_rows():
    conn = connect(":memory:")
    init_schema(conn)
    conn.execute(
        "INSERT INTO live_odds_snapshots"
        " (captured_at, game_key, commence_time, home_team, away_team,"
        "  cons_spread_home, cons_total, cons_ml_home, cons_ml_away)"
        " VALUES ('2026-09-01T12:00:00Z','2026-09-07_BUF_at_KC','2026-09-07T17:00:00Z',"
        "         'Kansas City Chiefs','Buffalo Bills',-2.5,48.5,-140,120)"
    )
    n = conn.execute("SELECT COUNT(*) FROM live_odds_snapshots").fetchone()[0]
    assert n == 1
    conn.close()
```

- [ ] **Step 2: Run → FAIL** (`uv run pytest tests/test_db.py -q`).

- [ ] **Step 3: Implement.** In `engine/db.py`, inside `_SCHEMA_SQL` before the closing triple-quote, add:
```sql

CREATE TABLE IF NOT EXISTS live_odds_snapshots (
    snapshot_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at      TEXT NOT NULL,
    game_key         TEXT NOT NULL,
    commence_time    TEXT NOT NULL,
    home_team        TEXT NOT NULL,
    away_team        TEXT NOT NULL,
    cons_spread_home REAL,
    cons_total       REAL,
    cons_ml_home     INTEGER,
    cons_ml_away     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_live_odds_game ON live_odds_snapshots(game_key, captured_at);
```

- [ ] **Step 4: Run → PASS** (file + full suite). If `test_db.py` has an "exact table set" assertion, add `live_odds_snapshots` to it.

- [ ] **Step 5: Commit.**
```bash
git add engine/db.py tests/test_db.py
git commit -m "feat(db): live_odds_snapshots table

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: The Odds API client (`ingestion/live_odds.py`)

**Files:** Create `ingestion/live_odds.py`, `tests/fixtures/odds_api_sample.json`, `tests/test_live_odds.py`.

- [ ] **Step 1: Create the sample fixture.** Write `tests/fixtures/odds_api_sample.json` (one game, two books — enough to test consensus median + best-line selection):
```json
[
  {
    "id": "evt1",
    "commence_time": "2026-09-07T17:00:00Z",
    "home_team": "Kansas City Chiefs",
    "away_team": "Buffalo Bills",
    "bookmakers": [
      {"key": "draftkings", "title": "DraftKings", "markets": [
        {"key": "spreads", "outcomes": [
          {"name": "Kansas City Chiefs", "price": -110, "point": -2.5},
          {"name": "Buffalo Bills", "price": -110, "point": 2.5}]},
        {"key": "totals", "outcomes": [
          {"name": "Over", "price": -110, "point": 48.5},
          {"name": "Under", "price": -110, "point": 48.5}]},
        {"key": "h2h", "outcomes": [
          {"name": "Kansas City Chiefs", "price": -140},
          {"name": "Buffalo Bills", "price": 120}]}
      ]},
      {"key": "fanduel", "title": "FanDuel", "markets": [
        {"key": "spreads", "outcomes": [
          {"name": "Kansas City Chiefs", "price": -108, "point": -3.0},
          {"name": "Buffalo Bills", "price": -112, "point": 3.0}]},
        {"key": "totals", "outcomes": [
          {"name": "Over", "price": -105, "point": 49.0},
          {"name": "Under", "price": -115, "point": 49.0}]},
        {"key": "h2h", "outcomes": [
          {"name": "Kansas City Chiefs", "price": -150},
          {"name": "Buffalo Bills", "price": 130}]}
      ]}
    ]
  }
]
```

- [ ] **Step 2: Write the failing tests.** Create `tests/test_live_odds.py`:
```python
"""Tests for ingestion.live_odds — parse a saved Odds API payload (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from ingestion.live_odds import GameOdds, parse_odds_payload

_FIX = Path(__file__).parent / "fixtures" / "odds_api_sample.json"


def _games():
    return parse_odds_payload(json.loads(_FIX.read_text(encoding="utf-8")))


def test_parses_one_game_canonical_teams():
    games = _games()
    assert len(games) == 1
    g = games[0]
    assert g.home_team == "Kansas City Chiefs"
    assert g.away_team == "Buffalo Bills"
    assert g.n_books == 2
    assert g.game_key == "2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs"


def test_consensus_is_median_home_perspective():
    g = _games()[0]
    # spread home: median(-2.5, -3.0) = -2.75 ; total: median(48.5, 49.0) = 48.75
    assert g.cons_spread_home == -2.75
    assert g.cons_total == 48.75
    # ml home: median(-140, -150) = -145 ; ml away: median(120, 130) = 125
    assert g.cons_ml_home == -145
    assert g.cons_ml_away == 125


def test_best_ml_is_highest_price_per_side():
    g = _games()[0]
    # home ML best = max(-140, -150) = -140 (DraftKings)
    assert g.best_ml_home[0] == "DraftKings"
    assert g.best_ml_home[2] == -140
    # away ML best = max(120, 130) = 130 (FanDuel)
    assert g.best_ml_away[0] == "FanDuel"
    assert g.best_ml_away[2] == 130


def test_best_spread_home_prefers_more_points_then_price():
    g = _games()[0]
    # home spread: FanDuel -3.0 vs DK -2.5 -> for the home favorite, -2.5 lays FEWER
    # points (better for a home backer) -> DK wins on point favorability.
    assert g.best_spread_home[0] == "DraftKings"
    assert g.best_spread_home[1] == -2.5


def test_best_total_over_prefers_lower_line():
    g = _games()[0]
    # over best = lowest total (48.5, DraftKings) -> easier to exceed
    assert g.best_total_over[0] == "DraftKings"
    assert g.best_total_over[1] == 48.5
    # under best = highest total (49.0, FanDuel)
    assert g.best_total_under[1] == 49.0


def test_unknown_team_skips_game_not_crash():
    payload = [{
        "id": "x", "commence_time": "2026-09-07T17:00:00Z",
        "home_team": "Springfield Isotopes", "away_team": "Buffalo Bills",
        "bookmakers": [],
    }]
    assert parse_odds_payload(payload) == []
```

- [ ] **Step 3: Run → FAIL.**

- [ ] **Step 4: Implement.** Create `ingestion/live_odds.py`:
```python
"""The Odds API client for live NFL odds.

Pure parse (parse_odds_payload) tested against a fixture; thin network boundary
(fetch_odds). Computes consensus (median across books, home-perspective) and the
best available price per side (line shopping). Key from ODDS_API_KEY env var.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from ingestion.team_names import canonicalize_team_name

_API = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
_ENV_FILE = Path(".env")

# best-line = (book_title, point_or_None, price)
BestLine = tuple[str, float | None, int]


@dataclass(frozen=True)
class GameOdds:
    game_key: str
    commence_time: str
    home_team: str
    away_team: str
    cons_spread_home: float | None
    cons_total: float | None
    cons_ml_home: int | None
    cons_ml_away: int | None
    best_spread_home: BestLine | None
    best_spread_away: BestLine | None
    best_total_over: BestLine | None
    best_total_under: BestLine | None
    best_ml_home: BestLine | None
    best_ml_away: BestLine | None
    n_books: int


def get_api_key() -> str | None:
    """Resolve ODDS_API_KEY from the environment, falling back to a gitignored .env."""
    key = os.getenv("ODDS_API_KEY")
    if key:
        return key.strip()
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ODDS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _game_key(commence_time: str, away: str, home: str) -> str:
    date = commence_time[:10]
    return f"{date}_{away.replace(' ', '_')}_at_{home.replace(' ', '_')}"


def _collect(bookmakers: list[dict], market_key: str, outcome_name: str) -> list[tuple[str, float | None, int]]:
    """Return (book_title, point, price) tuples for a given market+outcome across books."""
    out = []
    for bk in bookmakers:
        for m in bk.get("markets", []):
            if m.get("key") != market_key:
                continue
            for o in m.get("outcomes", []):
                if o.get("name") == outcome_name:
                    out.append((bk.get("title", bk.get("key", "?")), o.get("point"), int(o["price"])))
    return out


def _median_or_none(vals: list[float]) -> float | None:
    return median(vals) if vals else None


def _best(lines: list[tuple[str, float | None, int]], *, by_point: str | None) -> BestLine | None:
    """Pick the most favorable line.

    by_point=None  -> moneyline: best = highest price.
    by_point='max' -> bettor wants the highest point (home dog / spread away, under).
    by_point='min' -> bettor wants the lowest point  (home fav side handled by caller sign).
    Tie-break on price (higher better).
    """
    if not lines:
        return None
    if by_point is None:
        return max(lines, key=lambda t: t[2])
    sign = 1 if by_point == "max" else -1
    return max(lines, key=lambda t: (sign * (t[1] if t[1] is not None else 0.0), t[2]))


def parse_odds_payload(payload: list[dict]) -> list[GameOdds]:
    """Parse The Odds API JSON into GameOdds. Unknown teams skip the game (counted by absence)."""
    games: list[GameOdds] = []
    for evt in payload:
        try:
            home = canonicalize_team_name(evt["home_team"])
            away = canonicalize_team_name(evt["away_team"])
        except KeyError:
            continue
        bks = evt.get("bookmakers", [])
        raw_home, raw_away = evt["home_team"], evt["away_team"]

        sp_home = _collect(bks, "spreads", raw_home)
        sp_away = _collect(bks, "spreads", raw_away)
        tot_over = _collect(bks, "totals", "Over")
        tot_under = _collect(bks, "totals", "Under")
        ml_home = _collect(bks, "h2h", raw_home)
        ml_away = _collect(bks, "h2h", raw_away)

        games.append(GameOdds(
            game_key=_game_key(evt["commence_time"], away, home),
            commence_time=evt["commence_time"],
            home_team=home,
            away_team=away,
            cons_spread_home=_median_or_none([p for _b, p, _pr in sp_home if p is not None]),
            cons_total=_median_or_none([p for _b, p, _pr in tot_over if p is not None]),
            cons_ml_home=int(median([pr for _b, _p, pr in ml_home])) if ml_home else None,
            cons_ml_away=int(median([pr for _b, _p, pr in ml_away])) if ml_away else None,
            # home favorite lays points: fewer points (higher, toward 0) is better -> 'max'
            best_spread_home=_best(sp_home, by_point="max"),
            best_spread_away=_best(sp_away, by_point="max"),
            best_total_over=_best(tot_over, by_point="min"),   # lower total better for over
            best_total_under=_best(tot_under, by_point="max"),  # higher total better for under
            best_ml_home=_best(ml_home, by_point=None),
            best_ml_away=_best(ml_away, by_point=None),
            n_books=len(bks),
        ))
    return games


def fetch_odds(api_key: str | None = None) -> list[GameOdds]:
    """Fetch + parse current NFL odds. Raises RuntimeError with guidance if no key."""
    key = api_key or get_api_key()
    if not key:
        raise RuntimeError("ODDS_API_KEY not set — see .env.example. Never commit the key.")
    qs = urllib.parse.urlencode({
        "apiKey": key, "regions": "us", "markets": "spreads,totals,h2h", "oddsFormat": "american",
    })
    req = urllib.request.Request(f"{_API}?{qs}", headers={"User-Agent": "nfl-betting/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/raw/odds_api_latest.json").write_text(json.dumps(payload), encoding="utf-8")
    return parse_odds_payload(payload)
```
Note the spread sign: the API gives the home team's own `point` (e.g. -2.5 if home favored), which already matches our home-perspective convention. The test `test_best_spread_home_prefers_more_points_then_price` pins that for a home favorite, the line closer to 0 (fewer points laid) wins via `by_point='max'`.

- [ ] **Step 5: Run → PASS** (`uv run pytest tests/test_live_odds.py -q`, then full suite). Lint.

- [ ] **Step 6: Commit.**
```bash
git add ingestion/live_odds.py tests/test_live_odds.py tests/fixtures/odds_api_sample.json
git commit -m "feat(live_odds): The Odds API parse + consensus + best-line (line shopping)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Snapshot store (`ingestion/live_odds_store.py`)

**Files:** Create `ingestion/live_odds_store.py`, `tests/test_live_odds_store.py`.

- [ ] **Step 1: Failing tests.** Create `tests/test_live_odds_store.py`:
```python
from __future__ import annotations

from engine.db import connect, init_schema
from ingestion.live_odds import GameOdds
from ingestion.live_odds_store import current_consensus, opener_consensus, store_snapshot


def _g(spread, total, ml_home=-140, ml_away=120):
    return GameOdds(
        game_key="2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs",
        commence_time="2026-09-07T17:00:00Z",
        home_team="Kansas City Chiefs", away_team="Buffalo Bills",
        cons_spread_home=spread, cons_total=total, cons_ml_home=ml_home, cons_ml_away=ml_away,
        best_spread_home=None, best_spread_away=None, best_total_over=None,
        best_total_under=None, best_ml_home=None, best_ml_away=None, n_books=3,
    )


def test_store_and_read_opener_vs_current():
    conn = connect(":memory:")
    init_schema(conn)
    store_snapshot(conn, [_g(-2.5, 48.5)], captured_at="2026-09-03T12:00:00Z")
    store_snapshot(conn, [_g(-4.0, 49.5)], captured_at="2026-09-06T12:00:00Z")
    op = opener_consensus(conn)["2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs"]
    cur = current_consensus(conn)["2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs"]
    assert op["cons_spread_home"] == -2.5   # earliest
    assert cur["cons_spread_home"] == -4.0  # latest
    conn.close()
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.** Create `ingestion/live_odds_store.py`:
```python
"""Persist live-odds consensus snapshots and read opener (earliest) / current (latest)."""

from __future__ import annotations

import sqlite3

from ingestion.live_odds import GameOdds


def store_snapshot(conn: sqlite3.Connection, games: list[GameOdds], *, captured_at: str) -> int:
    """Insert one consensus row per game for this capture. Returns rows inserted."""
    n = 0
    for g in games:
        conn.execute(
            "INSERT INTO live_odds_snapshots"
            " (captured_at, game_key, commence_time, home_team, away_team,"
            "  cons_spread_home, cons_total, cons_ml_home, cons_ml_away)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (captured_at, g.game_key, g.commence_time, g.home_team, g.away_team,
             g.cons_spread_home, g.cons_total, g.cons_ml_home, g.cons_ml_away),
        )
        n += 1
    conn.commit()
    return n


def _consensus(conn: sqlite3.Connection, *, newest: bool) -> dict[str, dict]:
    order = "DESC" if newest else "ASC"
    rows = conn.execute(
        f"SELECT game_key, captured_at, commence_time, home_team, away_team,"
        f" cons_spread_home, cons_total, cons_ml_home, cons_ml_away"
        f" FROM live_odds_snapshots ORDER BY captured_at {order}"
    ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        key = r[0]
        if key in out:
            continue  # first seen wins (newest or earliest per `order`)
        out[key] = {
            "captured_at": r[1], "commence_time": r[2], "home_team": r[3], "away_team": r[4],
            "cons_spread_home": r[5], "cons_total": r[6], "cons_ml_home": r[7], "cons_ml_away": r[8],
        }
    return out


def opener_consensus(conn: sqlite3.Connection) -> dict[str, dict]:
    """Earliest stored consensus per game (our captured 'open')."""
    return _consensus(conn, newest=False)


def current_consensus(conn: sqlite3.Connection) -> dict[str, dict]:
    """Latest stored consensus per game."""
    return _consensus(conn, newest=True)
```

- [ ] **Step 4: Run → PASS** (file + full suite). Lint.

- [ ] **Step 5: Commit.**
```bash
git add ingestion/live_odds_store.py tests/test_live_odds_store.py
git commit -m "feat(live_odds): snapshot store + opener/current consensus readers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Board builder (`engine/this_week.py`)

**Files:** Create `engine/this_week.py`, `tests/test_this_week.py`.

- [ ] **Step 1: Failing tests.** Create `tests/test_this_week.py`:
```python
from __future__ import annotations

import math

from engine.this_week import ThisWeekGame, build_board, historical_spread_context


def test_historical_spread_context_looks_up_bucket():
    # uses the committed ats_by_bucket.csv; a home favorite of -3 maps to a bucket
    ctx = historical_spread_context(-3.0)
    assert ctx is None or (0.0 <= ctx["win_rate"] <= 1.0 and ctx["n"] > 0 and "bucket" in ctx)


def test_build_board_movement_and_best_price():
    games = [_make_game(cons_spread_home=-4.0, best_ml_home=("DK", None, -140))]
    openers = {games[0].game_key: {"cons_spread_home": -2.5, "cons_total": 48.0}}
    board = build_board(games, openers)
    assert len(board) == 1
    g = board[0]
    assert g.spread_move == -1.5            # current -4.0 - opener -2.5
    assert g.best_ml_home == ("DK", None, -140)
    assert g.matchup.endswith("Kansas City Chiefs")


def test_build_board_no_opener_yields_none_movement():
    games = [_make_game(cons_spread_home=-4.0)]
    board = build_board(games, openers={})
    assert board[0].spread_move is None


def test_build_board_empty():
    assert build_board([], {}) == []


# --- helper to build a GameOdds without importing the whole dataclass verbosely ---
def _make_game(cons_spread_home=-3.0, cons_total=47.0, best_ml_home=None):
    from ingestion.live_odds import GameOdds
    return GameOdds(
        game_key="2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs",
        commence_time="2026-09-07T17:00:00Z",
        home_team="Kansas City Chiefs", away_team="Buffalo Bills",
        cons_spread_home=cons_spread_home, cons_total=cons_total, cons_ml_home=-140, cons_ml_away=120,
        best_spread_home=("DK", cons_spread_home, -110), best_spread_away=("FD", -cons_spread_home, -110),
        best_total_over=("DK", cons_total, -110), best_total_under=("FD", cons_total, -110),
        best_ml_home=best_ml_home, best_ml_away=("FD", None, 120), n_books=3,
    )
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.** Create `engine/this_week.py`:
```python
"""Build the 'This Week' board from current GameOdds + stored opener consensus.

Per upcoming game: current consensus + best price per side (from live GameOdds),
line movement vs our earliest snapshot, and historical bucket context (spread/total
only — ML buckets are derived/biased, so no historical 'rate' is shown for ML).
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from engine.ats import bucket_spread
from engine.totals import bucket_total
from ingestion.live_odds import BestLine, GameOdds

_ATS_CSV = Path("data/processed/ats_by_bucket.csv")
_TOT_CSV = Path("data/processed/totals_by_bucket.csv")


@dataclass(frozen=True)
class ThisWeekGame:
    game_key: str
    matchup: str  # "Away at Home"
    commence_time: str
    cons_spread_home: float | None
    cons_total: float | None
    best_spread_home: BestLine | None
    best_spread_away: BestLine | None
    best_total_over: BestLine | None
    best_total_under: BestLine | None
    best_ml_home: BestLine | None
    best_ml_away: BestLine | None
    spread_move: float | None   # current - opener (home perspective)
    total_move: float | None
    spread_ctx: dict | None     # {bucket, win_rate, n} or None
    total_ctx: dict | None


def _lookup(csv_path: Path, bucket: str | None) -> dict | None:
    if bucket is None or not csv_path.exists():
        return None
    with csv_path.open(encoding="utf-8") as f:
        rows = [ln for ln in f if not ln.lstrip().startswith("#")]
    for row in csv.DictReader(rows):
        if row.get("bucket") == bucket:
            return {"bucket": bucket, "win_rate": float(row["win_rate"]), "n": int(row["n"])}
    return None


def historical_spread_context(spread_home: float | None) -> dict | None:
    """Historical ATS rate for the bucket a current home spread falls into (uncertified)."""
    if spread_home is None:
        return None
    return _lookup(_ATS_CSV, bucket_spread(spread_home))


def historical_total_context(total: float | None) -> dict | None:
    if total is None:
        return None
    return _lookup(_TOT_CSV, bucket_total(total))


def _move(current: float | None, opener: float | None) -> float | None:
    if current is None or opener is None:
        return None
    return round(current - opener, 2)


def build_board(games: list[GameOdds], openers: dict[str, dict]) -> list[ThisWeekGame]:
    """Assemble the board. `openers` maps game_key -> earliest consensus dict.

    Sorted by absolute spread movement desc (biggest movers first) — descriptive,
    not an edge ranking.
    """
    board: list[ThisWeekGame] = []
    for g in games:
        op = openers.get(g.game_key, {})
        board.append(ThisWeekGame(
            game_key=g.game_key,
            matchup=f"{g.away_team} at {g.home_team}",
            commence_time=g.commence_time,
            cons_spread_home=g.cons_spread_home,
            cons_total=g.cons_total,
            best_spread_home=g.best_spread_home,
            best_spread_away=g.best_spread_away,
            best_total_over=g.best_total_over,
            best_total_under=g.best_total_under,
            best_ml_home=g.best_ml_home,
            best_ml_away=g.best_ml_away,
            spread_move=_move(g.cons_spread_home, op.get("cons_spread_home")),
            total_move=_move(g.cons_total, op.get("cons_total")),
            spread_ctx=historical_spread_context(g.cons_spread_home),
            total_ctx=historical_total_context(g.cons_total),
        ))
    board.sort(key=lambda t: abs(t.spread_move) if t.spread_move is not None else -1.0, reverse=True)
    return board
```

- [ ] **Step 4: Run → PASS** (file + full suite). Lint.

- [ ] **Step 5: Commit.**
```bash
git add engine/this_week.py tests/test_this_week.py
git commit -m "feat(this_week): board builder (best price, movement, historical context)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Streamlit board (`app/`) + theme + secrets + deps

**Files:** Create `app/__init__.py`, `app/theme.py`, `app/this_week_view.py`, `app/main.py`, `.streamlit/config.toml`, `.env.example`, `tests/test_app_smoke.py`; modify `.gitignore`, `pyproject.toml`.

This task is a thin UI over the tested builder. The exact visual polish is iterated via `openwolf designqc` in Task 6 — here we build a correct, refined-dark, honest board that boots cleanly.

- [ ] **Step 1: Add deps + secret scaffolding.**
```bash
uv add streamlit altair
```
Append to `.gitignore`:
```
# Secrets
.env
.streamlit/secrets.toml
```
Create `.env.example`:
```
# Copy to .env (gitignored) or set in your shell. Never commit the real key.
ODDS_API_KEY=your-the-odds-api-key-here
```
Create `.streamlit/config.toml`:
```toml
[theme]
base = "dark"
primaryColor = "#6c8cff"
backgroundColor = "#14161c"
secondaryBackgroundColor = "#1b1e26"
textColor = "#e8eaf0"
font = "sans serif"
```

- [ ] **Step 2: Write the smoke test.** Create `tests/test_app_smoke.py`:
```python
"""Smoke test: the Streamlit app boots and renders without error (no live network)."""

from __future__ import annotations

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402


def test_app_boots_without_error():
    at = AppTest.from_file("app/main.py", default_timeout=30).run()
    assert not at.exception
```

- [ ] **Step 3: Run → FAIL** (`app/main.py` doesn't exist).

- [ ] **Step 4: Implement the app.**

`app/__init__.py`: empty.

`app/theme.py`:
```python
"""Refined-dark CSS polish injected into the Streamlit app."""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
  .block-container { padding-top: 2rem; max-width: 1100px; }
  .twg-card { background:#1b1e26; border:1px solid #262b36; border-radius:12px;
              padding:16px 18px; margin-bottom:14px; }
  .twg-matchup { font-size:18px; font-weight:700; color:#e8eaf0; }
  .twg-time { font-size:12px; color:#9aa0ad; }
  .twg-best { color:#8aa0ff; font-weight:700; }
  .twg-move-up { color:#2ea043; font-weight:600; }
  .twg-move-down { color:#f85149; font-weight:600; }
  .twg-ctx { font-size:12px; color:#9aa0ad; }
  .twg-banner { background:#1b1e26; border:1px solid #2e3a52; border-radius:10px;
                padding:12px 16px; color:#c9d1e0; font-size:13px; margin-bottom:18px; }
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


HONESTY_BANNER = (
    "**Context & best prices — not certified picks.** Historical rates are *not* a proven "
    "edge (the market is efficient — see the CLV finding). The real edge here is **line "
    "shopping**: take the best price. Line movement is descriptive. Past performance ≠ "
    "future results. Gamble responsibly."
)
```

`app/this_week_view.py`:
```python
"""Render the This Week board (thin view over engine.this_week.build_board)."""

from __future__ import annotations

import streamlit as st

from app.theme import HONESTY_BANNER
from engine.this_week import ThisWeekGame


def _fmt_best(b) -> str:
    if b is None:
        return "—"
    book, point, price = b
    sign = "+" if price > 0 else ""
    pt = "" if point is None else f"{point:+g} @ "
    return f"{pt}{sign}{price} ({book})"


def _move_html(move, *, lower_is_toward_home: bool = True) -> str:
    if move is None:
        return '<span class="twg-ctx">no opener captured yet</span>'
    cls = "twg-move-down" if move < 0 else "twg-move-up"
    arrow = "▼" if move < 0 else "▲"
    return f'<span class="{cls}">{arrow} {move:+g} since open</span>'


def render(board: list[ThisWeekGame]) -> None:
    st.markdown(f'<div class="twg-banner">{HONESTY_BANNER}</div>', unsafe_allow_html=True)
    if not board:
        st.info("No upcoming games / no odds captured yet. Pull odds with "
                "`uv run python -m ingestion.live_odds` (needs ODDS_API_KEY).")
        return
    st.caption(f"{len(board)} upcoming games · sorted by biggest line move")
    for g in board:
        spread_ctx = (f" · historical: {g.spread_ctx['win_rate']:.1%} cover "
                      f"(n={g.spread_ctx['n']}, not certified)") if g.spread_ctx else ""
        st.markdown(
            f'<div class="twg-card">'
            f'<div class="twg-matchup">{g.matchup}</div>'
            f'<div class="twg-time">{g.commence_time}</div>'
            f'<div style="margin-top:8px">'
            f'<b>Spread</b> (home): consensus {g.cons_spread_home:+g} · '
            f'best home <span class="twg-best">{_fmt_best(g.best_spread_home)}</span> · '
            f'best away <span class="twg-best">{_fmt_best(g.best_spread_away)}</span> · '
            f'{_move_html(g.spread_move)}<span class="twg-ctx">{spread_ctx}</span></div>'
            f'<div><b>Total</b>: consensus {g.cons_total:g} · '
            f'best over <span class="twg-best">{_fmt_best(g.best_total_over)}</span> · '
            f'best under <span class="twg-best">{_fmt_best(g.best_total_under)}</span></div>'
            f'<div><b>Moneyline</b>: best home <span class="twg-best">{_fmt_best(g.best_ml_home)}</span> · '
            f'best away <span class="twg-best">{_fmt_best(g.best_ml_away)}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
```

`app/main.py`:
```python
"""NFL Betting Analytics — live This Week odds board (Streamlit entry point)."""

from __future__ import annotations

import streamlit as st

from app import theme
from app.this_week_view import render as render_this_week
from engine.db import connect
from engine.this_week import build_board
from ingestion.live_odds import parse_odds_payload
from ingestion.live_odds_store import current_consensus, opener_consensus

_DB = "data/db/nfl_betting.sqlite"


@st.cache_data(show_spinner=False)
def _load_board():
    """Build the board from the latest stored snapshot (no live call on page load)."""
    import json
    from pathlib import Path

    raw = Path("data/raw/odds_api_latest.json")
    if not raw.exists():
        return []
    games = parse_odds_payload(json.loads(raw.read_text(encoding="utf-8")))
    try:
        conn = connect(_DB)
        openers = opener_consensus(conn)
        conn.close()
    except Exception:
        openers = {}
    return build_board(games, openers)


def main() -> None:
    st.set_page_config(page_title="NFL Odds — This Week", page_icon="🏈", layout="wide")
    theme.inject()
    st.title("This Week — live NFL odds")
    # Slice 9 adds sibling tabs (The Finding / Edge Report / CLV Explorer / Data & Audit).
    tab_week, = st.tabs(["This Week"])
    with tab_week:
        render_this_week(_load_board())


main()
```
Note: the app renders from the latest stored snapshot file (`data/raw/odds_api_latest.json`, written by `fetch_odds`) so page load never makes a live API call. The weekly pull (`python -m ingestion.live_odds`) refreshes that file + stores a snapshot. The smoke test runs with no file present → empty board → no exception.

- [ ] **Step 5: Add a `__main__` to `ingestion/live_odds.py`** so the weekly pull works. Append:
```python
def _main() -> int:
    from datetime import UTC, datetime

    from engine.db import connect, init_schema
    from ingestion.live_odds_store import store_snapshot
    try:
        games = fetch_odds()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 1
    conn = connect("data/db/nfl_betting.sqlite")
    init_schema(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    n = store_snapshot(conn, games, captured_at=now)
    conn.close()
    print(f"Fetched {len(games)} games; stored {n} consensus snapshots at {now}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
```
(Add `from datetime import ...` import at top instead if ruff prefers; keep imports tidy.)

- [ ] **Step 6: Run → PASS.** `uv run pytest tests/test_app_smoke.py -q` (AppTest boots, empty board, no exception), then `uv run pytest -q` full suite, then `uv run ruff check .`.

- [ ] **Step 7: Commit.**
```bash
git add app/ .streamlit/ .env.example .gitignore pyproject.toml uv.lock ingestion/live_odds.py tests/test_app_smoke.py
git commit -m "feat(app): refined-dark Streamlit This Week board + weekly-pull CLI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Live end-to-end, design polish, README, bookkeeping

**Files:** Modify `README.md`, `.wolf/memory.md`, `.wolf/cerebrum.md`. (No engine/test code.)

- [ ] **Step 1: Live pull (requires the user's key).** Confirm `ODDS_API_KEY` is set (the user sets it: `$env:ODDS_API_KEY="..."` in PowerShell, or a gitignored `.env`). Run:
```bash
uv run python -m ingestion.live_odds
```
Expected: "Fetched N games; stored N consensus snapshots…". If offseason (no NFL games this week), N may be 0 — that's fine; note it. If the key is missing, the friendly error fires (don't proceed until set). Confirm `data/raw/odds_api_latest.json` was written and `live_odds_snapshots` has rows:
```bash
uv run python -c "from engine.db import connect; print(connect('data/db/nfl_betting.sqlite').execute('SELECT COUNT(*) FROM live_odds_snapshots').fetchone()[0])"
```

- [ ] **Step 2: Launch + design QC.** Start the app (`streamlit run app/main.py` — runs until stopped) and run `openwolf designqc` to screenshot the board. Read the captured images from `.wolf/designqc-captures/`. Evaluate the refined-dark board against the look (spacing, hierarchy, the accent, card readability, the honesty banner prominence). Apply polish tweaks to `app/theme.py` / `app/this_week_view.py` as needed and re-capture. (If offseason and the board is empty, capture the empty-state + seed a couple of `data/raw/odds_api_latest.json` sample games from the fixture to screenshot a populated board.)

- [ ] **Step 3: README.** Add a "## Slice 8 — Live This Week odds board" section: what it does (best price / line shopping + movement + historical context), the honest framing, setup (get a free key at the-odds-api.com, set `ODDS_API_KEY` via env or gitignored `.env` — never commit it), the weekly pull command, and `streamlit run app/main.py`. Add a Scope bullet: "**Slice 8 (complete):** live This Week odds board — current odds + best price (line shopping) + line movement + historical context, refined-dark Streamlit, honest framing. Historical showcase tabs = Slice 9." Keep the disclaimer.

- [ ] **Step 4: Bookkeeping.** `.wolf/memory.md` one Slice 8 line; `.wolf/cerebrum.md` Decision Log entry (live-first pivot; "best odds = line shopping"; honesty rails; secret via env). Re-read top of memory.md first; retry once if the hook modified it.

- [ ] **Step 5: Final verify + commit.**
```bash
uv run pytest -q
uv run ruff check .
git add README.md .wolf/memory.md .wolf/cerebrum.md app/ 2>/dev/null
git status   # confirm NO .env, no data/db, no data/raw/odds_api_latest.json, no key anywhere staged
git commit -m "docs(slice8): This Week board polish + README + bookkeeping

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage:**
- Live odds fetch + parse + consensus + best price (line shopping) → Task 2. ✓
- `live_odds_snapshots` + opener/current → Tasks 1, 3. ✓
- Board builder (best price, movement, historical context spread/total) → Task 4. ✓
- Refined-dark Streamlit board + honesty banner + empty state → Task 5. ✓
- Secret handling (env var + .env + .env.example + gitignore; missing-key message) → Tasks 2 (`get_api_key`/`fetch_odds`), 5. ✓
- Deps streamlit+altair, urllib fetch → Task 5 / Task 2. ✓
- Tests (parse fixture, store, builder, db, AppTest smoke) → Tasks 1-5. ✓
- End-to-end live pull + designqc + README + bookkeeping → Task 6. ✓
- Honesty rails (banner, sort by movement not edge, ML no historical rate) → Tasks 4, 5. ✓
- Out of scope (historical tabs Slice 9; no edge ranking) → respected. ✓

**Placeholder scan:** complete code in Tasks 1-4; Task 5 UI is full code (view polish iterated via designqc in Task 6, which is the honest iterative step for UI); Task 6 is operational. No TBD. `altair` is added (Task 5) for future charts though the first board is HTML cards — acceptable (Slice 9 charts use it); if YAGNI-strict, the implementer may defer altair, but the spec lists it. ✓

**Type consistency:** `GameOdds` fields identical across `live_odds.py` (def), the store, the builder tests, and `this_week.py`. `BestLine = (book, point|None, price)` used consistently. `ThisWeekGame` fields match between `this_week.py` and the view. Function names consistent: `parse_odds_payload`, `fetch_odds`, `get_api_key`, `store_snapshot`, `opener_consensus`, `current_consensus`, `build_board`, `historical_spread_context`/`historical_total_context`. ✓

**Note for executor:** the spread best-line favorability rule (`by_point='max'` for the home side = fewest points laid) is the subtle correctness point — Task 2's tests pin it. Verify against the fixture before moving on.
