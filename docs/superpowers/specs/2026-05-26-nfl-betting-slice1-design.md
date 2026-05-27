# NFL Betting Analytics — Slice 1 Design

**Date:** 2026-05-26
**Status:** Draft for review
**Scope:** First slice of the NFL Sports Betting Analytics Engine. Foundation only.

---

## 1. Purpose

Build the smallest end-to-end pipeline that proves the foundation works:

1. Raw NFL data (2004–2024) loaded into a local database.
2. A reusable statistics utility module with hand-verified math.
3. One real ATS (against-the-spread) analysis with full statistical rigor — sample size, win rate, ROI at -110 and -105, p-value vs the 52.38% breakeven, 95% confidence interval, by-season trend.
4. A unit-tested test suite that lets us trust every number in the output.

When Slice 1 is done, running a single command produces a publication-quality ATS-by-spread-bucket table for the full 20-year dataset, and we can confidently say "the math is right and the data is real" before scaling to dozens of other analyses.

Slice 1 is intentionally narrow. The full vision (totals, moneyline, composites, regression, bankroll sim, dashboard, API, live odds, line movement, scraping) is deferred to later slices, each with its own spec.

---

## 2. Non-Goals (explicitly NOT in Slice 1)

- Totals (over/under) analysis
- Moneyline analysis (data also limited in the Slice 1 source)
- Composite/multi-factor analyses
- Regression or ML models
- Kelly sizing or bankroll simulation (the Kelly *utility function* is built and tested, but no simulator)
- Web dashboard, FastAPI, live odds, alerts
- Multiple book sources or line movement
- Web scraping (Pro-Football-Reference, SportsOddsHistory, Covers) — deferred to a later slice
- Production deployment, Docker, CI

---

## 3. Data

### Source
**Kaggle "NFL Scores and Betting Data"** — `spreadspoke_scores.csv` (and the companion `nfl_teams.csv` for team metadata if present).

Reasons for starting here:
- Legal and stable (bulk CSV; no scraper fragility).
- Covers ~1979–present, includes home/away teams, scores, spread (favorite-relative), over/under line, weather, stadium info, schedule fields.
- Lets us move past data acquisition immediately and focus on math.

Scrapers and additional sources (opening lines, moneylines, line movement, public betting %) are deferred to Slice 2+.

### Filter
Restrict to `season >= 2004 AND season <= 2024` for Slice 1.

### Storage
**SQLite** at `data/db/nfl_betting.sqlite`. Stdlib `sqlite3` only — no ORM at this scale.

Raw CSVs land in `data/raw/`. The cleaned ATS output CSV lands in `data/processed/`.

### Known data caveats Slice 1 must handle
- **Team name history (2004–2024 era):** Houston Oilers→Tennessee Oilers→Tennessee Titans (pre-window); St. Louis Rams→Los Angeles Rams (2016); San Diego Chargers→Los Angeles Chargers (2017); Oakland Raiders→Las Vegas Raiders (2020); Washington Redskins→Washington Football Team→Washington Commanders. Loader normalizes to a single canonical name per franchise via a lookup table.
- **Spread sign convention:** The Kaggle CSV stores the spread as a single magnitude with a separate "team favorite" identifier. The loader converts this to `spread_home_close` (negative = home favored, positive = home underdog, 0 = pick'em).
- **Division realignment:** The 2002 realignment is already in effect for our window, so a single static divisions table works. (Future slices that go pre-2002 will need eras.)
- **Missing fields:** Some games (especially older or international) may have `NULL` weather, total, or spread. Loader records them as NULL; analysis skips rows where the required field is NULL and reports skipped counts.
- **Push handling:** A push (e.g., -3 with a 3-point final margin) is neither a win nor a loss. ROI treats pushes as stake-returned. Statistical tests exclude pushes from the denominator unless explicitly stated.

---

## 4. Database Schema

Three tables. Indexes on common lookup columns.

### `games`
| column | type | notes |
|---|---|---|
| game_id | TEXT PK | `{season}_{week}_{away}_{home}` — deterministic, idempotent |
| season | INTEGER | |
| week | INTEGER | regular-season week, or 100+ for playoffs (100=wildcard, 101=div, 102=conf, 103=SB) |
| game_date | TEXT (ISO 8601) | |
| home_team | TEXT | canonical name |
| away_team | TEXT | canonical name |
| home_score | INTEGER | NULL if game not yet played |
| away_score | INTEGER | |
| stadium | TEXT | |
| dome_flag | INTEGER (0/1) | derived from stadium lookup |
| weather_temp | INTEGER | F; NULL if dome or unknown |
| weather_wind | INTEGER | mph; NULL if dome or unknown |
| weather_humidity | INTEGER | %; NULL where unknown |
| primetime_flag | INTEGER (0/1) | SNF/MNF/TNF — derived from game_date day-of-week + time if available, else schedule heuristic |
| playoff_flag | INTEGER (0/1) | |
| division_game_flag | INTEGER (0/1) | derived via `team_divisions` join |

Index: `(season, week)`, `(home_team)`, `(away_team)`.

### `betting_lines`
| column | type | notes |
|---|---|---|
| line_id | INTEGER PK AUTOINCREMENT | |
| game_id | TEXT FK → games | |
| spread_home_close | REAL | negative = home favored |
| total_close | REAL | |
| home_spread_result | TEXT | `'cover' \| 'push' \| 'loss'` from home POV; NULL if line or score missing |
| total_result | TEXT | `'over' \| 'push' \| 'under'`; NULL if line or score missing |

Index: `(game_id)`.

Slice 1 inserts exactly one row per game (single consensus close). Multi-book support is deferred.

### `team_divisions`
Static seed table loaded once at DB-init time.

| column | type |
|---|---|
| team | TEXT PK |
| conference | TEXT (`AFC` / `NFC`) |
| division | TEXT (`North` / `South` / `East` / `West`) |

Source: hard-coded constant in `ingestion/divisions.py` (32 rows). Authoritative for 2002–present.

---

## 5. Module Layout

```
sports-betting/
├── pyproject.toml          # uv-managed deps, ruff config, pytest config
├── uv.lock
├── README.md
├── data/
│   ├── raw/                # spreadspoke_scores.csv lives here (gitignored)
│   ├── processed/          # ats_by_bucket.csv output
│   └── db/                 # nfl_betting.sqlite (gitignored)
├── ingestion/
│   ├── __init__.py
│   ├── divisions.py        # static 32-team division lookup
│   ├── team_names.py       # historical → canonical name map
│   ├── stadiums.py         # stadium → dome_flag, lat/lon (small static map)
│   └── loader.py           # CSV → cleaned rows → SQLite upsert
├── engine/
│   ├── __init__.py
│   ├── db.py               # connect(), schema init, simple query helpers
│   ├── stats_utils.py      # ROI, p-value, Wilson CI, Kelly, american↔decimal
│   └── ats.py              # ats_by_spread_bucket(), CLI entry
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── games_5.csv           # 5-game loader fixture (hand-built)
│   │   ├── games_20_ats.csv      # 20-game ATS bucket fixture
│   │   └── expected_*.json       # hand-verified expected outputs
│   ├── test_stats_utils.py
│   ├── test_loader.py
│   └── test_ats.py
└── docs/
    └── superpowers/specs/2026-05-26-nfl-betting-slice1-design.md
```

`.gitignore` excludes `data/raw/`, `data/db/`, `data/processed/`, `__pycache__/`, `.venv/`, `.ruff_cache/`, `.pytest_cache/`.

---

## 6. Component Specs

### 6.1 `engine/stats_utils.py`

Pure functions. No I/O. Each has a docstring citing the formula and a unit test with hand-verified expected output cross-checked against `scipy.stats`.

```python
def american_to_decimal(odds: int) -> float: ...
    # -110 → 1.9091; +150 → 2.50

def decimal_to_american(decimal_odds: float) -> int: ...

def roi(wins: int, losses: int, pushes: int = 0, american_odds: int = -110) -> float:
    """
    Flat-unit ROI assuming 1 unit risked per bet. Pushes return stake (0 PnL).
    Returns (profit_units) / (total_bets_including_pushes).
    Example: 55W / 45L at -110 → ROI = (55*0.9091 - 45) / 100 = +0.05005
    """

def binomial_pvalue(wins: int, n: int, breakeven: float = 0.5238) -> float:
    """
    One-sided exact binomial test: P(X >= wins | n, breakeven).
    Used to ask "is this win rate significantly better than -110 breakeven?"
    Cross-checked against scipy.stats.binomtest.
    """

def wilson_ci(wins: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """
    Wilson score interval for a proportion. Better than normal-approx at small n.
    """

def kelly_fraction(p_win: float, decimal_odds: float) -> float:
    """
    Optimal Kelly bet fraction. Built for future slices; tested now.
    f* = (p*b - (1-p)) / b, where b = decimal_odds - 1. Clamped to >= 0.
    """
```

**Breakeven constants:** `BREAKEVEN_AT_NEG_110 = 0.5238095…` (= 110/210), `BREAKEVEN_AT_NEG_105 = 0.51220…` (= 105/205).

### 6.2 `ingestion/loader.py`

Single entry point: `load_csv_to_db(csv_path: Path, db_path: Path, season_min=2004, season_max=2024) -> LoadReport`.

Steps:
1. Init DB (create tables, seed `team_divisions` and stadium lookups) if not present.
2. Read CSV with pandas; coerce types.
3. Filter to season range.
4. Normalize team names via `team_names.py`.
5. Derive `spread_home_close` from `(spread_favorite, team_favorite_id, home_team, away_team)`.
6. Derive `dome_flag` from `stadiums.py` (small hard-coded map; unknown stadium → 0).
7. Derive `division_game_flag` from `team_divisions`.
8. Derive `primetime_flag`: heuristic on day-of-week + week + season (TNF starts 2006). Document the heuristic in code; perfect precision not required for Slice 1 (this gets refined in later slices).
9. Derive `playoff_flag` from `schedule_playoff`. Map `schedule_week` string values: `"1"`–`"18"` → integer; `"Wildcard"` → 100, `"Division"` → 101, `"Conference"` → 102, `"Superbowl"` → 103.
10. Compute `home_spread_result` and `total_result` from final scores.
11. Idempotent upsert: `INSERT OR REPLACE` keyed on `game_id`. Re-running is a no-op when input unchanged.
12. Return a `LoadReport` dataclass: rows_read, rows_inserted, rows_skipped_missing_spread, rows_skipped_missing_score, by-season counts.

All step counts are logged to stdout for the reproducibility requirement.

### 6.3 `engine/ats.py`

Single proof-of-concept analysis. CLI entry: `python -m engine.ats`.

Function: `ats_by_spread_bucket(conn) -> AtsReport`

Buckets (home POV):
- Home favorite: `-14.5 to lower`, `-10.5 to -14`, `-7.5 to -10`, `-3.5 to -7`, `-1 to -3` (covers -1.0 to -3.0 inclusive; -0.5 and pick'em go to a "pick'em" bucket)
- Pick'em: `spread in (-0.5, 0, +0.5)` — small, reported separately for honesty
- Home underdog: `+1 to +3`, `+3.5 to +7`, `+7.5 to +10`, `+10.5 to +14`, `+14.5+`

For each bucket, output:
- `n` (excluding NULL spreads)
- `wins`, `losses`, `pushes` (home side cover counts)
- `win_rate` = wins / (wins + losses)
- `push_rate` = pushes / n
- `roi_neg110`, `roi_neg105` (via `stats_utils.roi`)
- `p_value` (binomial vs 0.5238)
- `ci_low`, `ci_high` (Wilson 95%)
- `insufficient_sample` flag if `wins + losses < 50`
- `by_season`: per-season win rate (sparkline-ready), for trend inspection

Outputs:
1. Pretty-printed table to stdout (use `tabulate` or hand-rolled formatter — `tabulate` is fine).
2. CSV at `data/processed/ats_by_bucket.csv`.
3. Trailing disclaimer line:
   > Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

### 6.4 `engine/db.py`

Thin helpers: `connect(path) -> sqlite3.Connection`, `init_schema(conn)`, `fetch_df(conn, sql, params) -> pd.DataFrame`. Foreign keys ON. Row factory = `sqlite3.Row`.

---

## 7. Testing Strategy

`pytest`. Every public function has at least one hand-verified test. No mocked databases — tests use real SQLite (in-memory or temp file).

### `test_stats_utils.py`
- `american_to_decimal(-110)` → `1.909090…` (within 1e-6)
- `roi(55, 45, 0, -110)` → `+0.05` exact (55 wins * 10/11 - 45 losses = 5; / 100 bets)
- `roi(50, 50, 0, -110)` → `-0.04545…` (50 * 10/11 - 50 = -4.5454…; / 100)
- `roi(53, 47, 0, -110)` → `+0.01182` (above breakeven; reference value 52.38W/47.62L → ROI ≈ 0)
- `roi(10, 10, 5, -110)` → ROI = (10 * 10/11 - 10) / 25 = -0.03636…; pushes inflate denominator only
- `binomial_pvalue(60, 100, 0.5238)` — cross-check against `scipy.stats.binomtest(60, 100, 0.5238, alternative='greater').pvalue`
- `wilson_ci(55, 100)` — expected ≈ (0.4524, 0.6439) within 1e-4 tolerance (cross-checked against hand calc with z=1.96)
- `kelly_fraction(0.55, 10/11 + 1)` → `0.055` exact ((0.55 * 10/11 - 0.45) / (10/11) = 0.055)

### `test_loader.py`
Hand-built `tests/fixtures/games_5.csv` with 5 games chosen to exercise every derivation:
1. Indoor primetime division game with a home cover.
2. Outdoor cold-weather game with a push on the spread.
3. Pick'em (spread 0) with a home win straight up.
4. Playoff wildcard game with home dog covering.
5. Game with missing total → verify NULL handling.

Test asserts each derived column matches a hand-written expected JSON.

### `test_ats.py`
Hand-built `tests/fixtures/games_20_ats.csv` with 20 games spread across buckets, designed so each populated bucket has known wins/losses/pushes. Test asserts the report matches an expected JSON exactly (counts, win_rate, ROI to 4 decimals, p-value to 4 decimals).

Also: an `insufficient_sample` test where one bucket has n=12 → flag is True.

### Coverage target
No formal coverage gate for Slice 1. Every public function in `engine/` and `ingestion/` must have at least one direct test.

---

## 8. Tooling

- **Python:** 3.11+
- **Deps:** `uv` for package management. `pyproject.toml` lists: `pandas`, `numpy`, `scipy`, `tabulate`, `pytest` (dev), `ruff` (dev). No ORM, no plotting yet (deferred to report slice).
- **Lint/format:** `ruff check` and `ruff format`. Config in `pyproject.toml`.
- **Test runner:** `pytest`. Config in `pyproject.toml`.
- **Run commands** (documented in README):
  - `uv sync` — install deps
  - `uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv` — load DB
  - `uv run python -m engine.ats` — produce ATS report
  - `uv run pytest` — run tests
  - `uv run ruff check . && uv run ruff format --check .` — lint

---

## 9. Compliance & Constraints (from the original prompt)

- Statistical rigor: every reported number ships with n, win rate, ROI, p-value, CI. `insufficient_sample` flag at n<50. ✓ Built into `AtsReport`.
- No survivorship bias: Slice 1 is descriptive, not predictive. Walk-forward CV applies in later slices when models exist.
- Account for juice: ROI reported at both -110 and -105. ✓
- 52.38% breakeven bar: p-values tested against this constant. ✓
- Decay detection: `by_season` win rate per bucket included so we can eyeball decay. Formal change-point detection is deferred.
- Responsible gambling disclaimer: appended to every stdout output and every CSV header line. ✓
- Reproducibility: no randomness in Slice 1. Logging of every transformation in the loader.

---

## 10. Definition of Done

1. Repo scaffolded per Section 5; `uv sync` succeeds on a fresh checkout.
2. `uv run pytest` passes; every public function has a direct test.
3. `uv run ruff check .` passes.
4. With `spreadspoke_scores.csv` present at `data/raw/`, `uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv` populates the DB and prints a load report; re-running is a no-op (idempotent verified).
5. `uv run python -m engine.ats` prints a populated table for 2004–2024 and writes `data/processed/ats_by_bucket.csv`, both with the disclaimer.
6. README documents the four commands above.
7. This spec is in the repo and committed.

---

## 11. What Comes Next (preview of later slices)

- **Slice 2:** Rest of Phase 2 analytics — totals, moneyline (needs supplemental data source), the remaining ATS dimensions (key numbers, primetime, division, weather, rest, line-movement once we have opens), composite stacking, decay detection.
- **Slice 3:** Static report generator (HTML + Markdown, charts).
- **Slice 4:** Streamlit dashboard.
- **Slice 5:** FastAPI + live odds + alerts.

Each gets its own spec → plan → build cycle.
