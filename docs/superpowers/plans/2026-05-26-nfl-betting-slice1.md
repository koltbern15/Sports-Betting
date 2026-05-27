# NFL Betting Analytics — Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end pipeline that loads 2004–2024 NFL games into SQLite and produces a publication-quality ATS-by-spread-bucket report with full statistical rigor (n, win rate, ROI at -110/-105, p-value, 95% CI, by-season trend).

**Architecture:** Python 3.11+ project, `uv`-managed. Pure-function stats library + idempotent CSV-to-SQLite loader + analysis module that joins games & lines and produces a tabular report. SQLite via stdlib (no ORM). TDD throughout: every public function lands with a hand-verified test before the implementation.

**Tech Stack:** Python 3.11+, `uv`, `pandas`, `numpy`, `scipy`, `tabulate`, `pytest`, `ruff`, SQLite (stdlib).

**Spec:** `docs/superpowers/specs/2026-05-26-nfl-betting-slice1-design.md`

---

## Conventions used throughout this plan

- **All commands run from the project root** `C:\Users\ktber\projects\sports-betting`.
- **All commands assume PowerShell.** Where path separators matter, forward slashes are fine on Windows in `uv` / `pytest` arguments.
- **Every task ends with a commit.** Commit messages follow Conventional Commits (`feat:`, `test:`, `chore:`, `docs:`).
- **Run `uv run pytest -q` after each task** to confirm nothing previously green has gone red.
- **Imports in test files:** project uses src-style with packages at the repo root (`engine/`, `ingestion/`), so test imports look like `from engine.stats_utils import roi`. `pyproject.toml` configures pytest with `pythonpath = ["."]` (set up in Task 1).
- **Constants used in tests** (defined in Task 3):
  - `BREAKEVEN_AT_NEG_110 = 110/210` ≈ `0.5238095…`
  - `BREAKEVEN_AT_NEG_105 = 105/205` ≈ `0.51219…`

---

## File-level decomposition (locked in here)

| File | Responsibility |
|---|---|
| `pyproject.toml` | deps, pytest config, ruff config |
| `.gitignore` | exclude data/raw, data/db, data/processed, venv, caches |
| `README.md` | how to install, ingest, run analysis, run tests |
| `engine/__init__.py` | empty marker |
| `engine/stats_utils.py` | pure stats functions: odds conversion, ROI, p-value, Wilson CI, Kelly |
| `engine/db.py` | sqlite connection + schema init + small query helpers |
| `engine/ats.py` | ATS-by-spread-bucket analysis + CLI |
| `ingestion/__init__.py` | empty marker |
| `ingestion/divisions.py` | 32-team static division lookup |
| `ingestion/team_names.py` | historical → canonical team-name mapping |
| `ingestion/stadiums.py` | stadium → dome_flag lookup |
| `ingestion/loader.py` | pure derivation helpers + `load_csv_to_db()` orchestrator |
| `tests/__init__.py` | empty marker |
| `tests/conftest.py` | shared fixtures (in-memory DB, tmp data dirs) |
| `tests/fixtures/games_5.csv` | hand-built 5-game loader fixture |
| `tests/fixtures/games_20_ats.csv` | hand-built 20-game ATS fixture |
| `tests/test_stats_utils.py` | tests for stats_utils |
| `tests/test_static_data.py` | sanity tests for divisions / team_names / stadiums |
| `tests/test_db.py` | tests for db helpers |
| `tests/test_loader_helpers.py` | tests for pure loader derivation funcs |
| `tests/test_loader.py` | end-to-end CSV → DB tests |
| `tests/test_ats.py` | tests for ATS analysis module |

---

## Task 1: Project scaffold

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `engine/__init__.py`
- Create: `ingestion/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `data/raw/.gitkeep`
- Create: `data/processed/.gitkeep`
- Create: `data/db/.gitkeep`

- [ ] **Step 1: Initialize git repo**

```powershell
git init
git branch -M main
```

Expected: `Initialized empty Git repository...` and main branch.

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Caches
.ruff_cache/
.pytest_cache/

# Data (large + non-reproducible artifacts)
data/raw/*
!data/raw/.gitkeep
data/processed/*
!data/processed/.gitkeep
data/db/*
!data/db/.gitkeep

# IDE / OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# uv
uv.lock
```

(Note: keeping `uv.lock` *un*tracked for Slice 1 to avoid noise from lockfile churn during early dev. Will be re-evaluated for prod.)

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "nfl-betting-analytics"
version = "0.1.0"
description = "NFL historical betting analytics engine (Slice 1: ingestion + ATS)"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "scipy>=1.13",
    "tabulate>=0.9",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B"]
```

- [ ] **Step 4: Create empty package markers and placeholder data dirs**

```powershell
New-Item -ItemType File engine/__init__.py
New-Item -ItemType File ingestion/__init__.py
New-Item -ItemType File tests/__init__.py
New-Item -ItemType Directory data/raw, data/processed, data/db -Force
New-Item -ItemType File data/raw/.gitkeep, data/processed/.gitkeep, data/db/.gitkeep
```

- [ ] **Step 5: Create `tests/conftest.py`** (shared fixtures used later)

```python
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
```

- [ ] **Step 6: Create `README.md` skeleton**

```markdown
# NFL Betting Analytics

> Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

Slice 1: ingestion + SQLite schema + statistics utilities + ATS-by-spread-bucket analysis.

See `docs/superpowers/specs/2026-05-26-nfl-betting-slice1-design.md` for the design.

## Setup

```powershell
uv sync
```

## Run tests

```powershell
uv run pytest
```

## Ingest data (Slice 1: Kaggle CSV only)

Place `spreadspoke_scores.csv` into `data/raw/` (Kaggle "NFL Scores and Betting Data").

```powershell
uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv
```

## Generate the ATS report

```powershell
uv run python -m engine.ats
```

Output: pretty-printed table to stdout and `data/processed/ats_by_bucket.csv`.
```

- [ ] **Step 7: Install deps and sanity-check pytest discovery**

```powershell
uv sync
uv run pytest --collect-only
```

Expected: `uv sync` resolves and installs deps. `pytest --collect-only` reports `0 tests collected` (no tests yet) without import errors.

- [ ] **Step 8: Sanity-check ruff**

```powershell
uv run ruff check .
```

Expected: `All checks passed!` (or no findings).

- [ ] **Step 9: Commit**

This is the first commit, so it sweeps in the pre-existing project files (`CLAUDE.md`, `.wolf/`, `.claude/`, the design doc, and this plan) alongside the scaffold. `.gitignore` excludes data/raw/data/processed/data/db contents (except the `.gitkeep` markers) and `.venv/` from this commit.

```powershell
git add .
git commit -m "chore: scaffold project with uv, pytest, ruff"
```

Sanity-check what was committed:

```powershell
git ls-files | Measure-Object -Line
```

Expected: somewhere around 15-25 files. Confirm `docs/superpowers/specs/2026-05-26-nfl-betting-slice1-design.md` and `docs/superpowers/plans/2026-05-26-nfl-betting-slice1.md` are both in the list:

```powershell
git ls-files docs/
```

---

## Task 2: stats_utils — odds conversion

**Files:**
- Create: `engine/stats_utils.py`
- Create: `tests/test_stats_utils.py`

- [ ] **Step 1: Write failing test**

In `tests/test_stats_utils.py`:

```python
import math

from engine.stats_utils import american_to_decimal, decimal_to_american


def test_american_to_decimal_negative():
    # -110 → 1 + 100/110 = 1.909090...
    assert math.isclose(american_to_decimal(-110), 1 + 100 / 110, rel_tol=0, abs_tol=1e-9)


def test_american_to_decimal_positive():
    # +150 → 1 + 150/100 = 2.50
    assert math.isclose(american_to_decimal(150), 2.50, abs_tol=1e-9)


def test_decimal_to_american_negative():
    # 1.909090... → -110
    assert decimal_to_american(1 + 100 / 110) == -110


def test_decimal_to_american_positive():
    # 2.50 → +150
    assert decimal_to_american(2.50) == 150


def test_roundtrip_negative():
    assert decimal_to_american(american_to_decimal(-110)) == -110


def test_roundtrip_positive():
    assert decimal_to_american(american_to_decimal(150)) == 150
```

- [ ] **Step 2: Run test, expect failure**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: ImportError / collection error (module/functions don't exist).

- [ ] **Step 3: Implement `engine/stats_utils.py`**

```python
"""Pure statistics utilities for sports-betting analysis.

All functions in this module are deterministic and side-effect-free.
"""

from __future__ import annotations

import math

BREAKEVEN_AT_NEG_110: float = 110 / 210  # ≈ 0.5238095…
BREAKEVEN_AT_NEG_105: float = 105 / 205  # ≈ 0.5121951…


def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal odds.

    Negative odds: pays 100/|odds| per unit risked.
    Positive odds: pays odds/100 per unit risked.
    """
    if odds == 0:
        raise ValueError("American odds of 0 are undefined")
    if odds < 0:
        return 1.0 + 100.0 / abs(odds)
    return 1.0 + odds / 100.0


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds back to American odds (rounded to nearest integer)."""
    if decimal_odds <= 1.0:
        raise ValueError("Decimal odds must be > 1.0")
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1.0) * 100)
    return -round(100.0 / (decimal_odds - 1.0))
```

- [ ] **Step 4: Run tests, expect pass**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```powershell
git add engine/stats_utils.py tests/test_stats_utils.py
git commit -m "feat(stats): american/decimal odds conversion"
```

---

## Task 3: stats_utils — ROI

**Files:**
- Modify: `engine/stats_utils.py` (append)
- Modify: `tests/test_stats_utils.py` (append)

- [ ] **Step 1: Append failing tests** to `tests/test_stats_utils.py`

```python
import math

from engine.stats_utils import roi


def test_roi_break_even_at_neg110_using_round_numbers():
    # 55W/45L at -110: 55 * 10/11 = 50.0 exactly; net = +5; ROI = 5/100 = 0.05
    assert math.isclose(roi(55, 45, 0, -110), 0.05, abs_tol=1e-12)


def test_roi_losing_record_at_neg110():
    # 50W/50L at -110: 50*10/11 - 50 = -4.5454...; / 100 = -0.045454...
    assert math.isclose(roi(50, 50, 0, -110), -50 / 11 / 100, abs_tol=1e-12)


def test_roi_pushes_only_inflate_denominator():
    # 10W/10L/5P at -110: net PnL = 10*10/11 - 10 = -10/11; bets = 25
    assert math.isclose(roi(10, 10, 5, -110), -(10 / 11) / 25, abs_tol=1e-12)


def test_roi_plus_money():
    # 30W/70L at +150: net = 30*1.5 - 70 = -25; bets = 100; ROI = -0.25
    assert math.isclose(roi(30, 70, 0, 150), -0.25, abs_tol=1e-12)


def test_roi_zero_bets_returns_zero():
    assert roi(0, 0, 0, -110) == 0.0
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: collection error (`roi` not defined).

- [ ] **Step 3: Append `roi` to `engine/stats_utils.py`**

```python
def roi(wins: int, losses: int, pushes: int = 0, american_odds: int = -110) -> float:
    """Flat-unit ROI assuming 1 unit risked per bet.

    Pushes return stake (0 PnL) but still count in the denominator
    because the bettor tied up 1 unit on each.
    """
    total = wins + losses + pushes
    if total == 0:
        return 0.0
    profit_per_win = american_to_decimal(american_odds) - 1.0
    pnl = wins * profit_per_win - losses
    return pnl / total
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```powershell
git add engine/stats_utils.py tests/test_stats_utils.py
git commit -m "feat(stats): flat-unit ROI with push handling"
```

---

## Task 4: stats_utils — binomial p-value

**Files:**
- Modify: `engine/stats_utils.py` (append)
- Modify: `tests/test_stats_utils.py` (append)

- [ ] **Step 1: Append failing tests**

```python
from scipy.stats import binomtest as _scipy_binomtest

from engine.stats_utils import BREAKEVEN_AT_NEG_110, binomial_pvalue


def test_binomial_pvalue_matches_scipy_60_of_100():
    expected = _scipy_binomtest(60, 100, BREAKEVEN_AT_NEG_110, alternative="greater").pvalue
    assert math.isclose(binomial_pvalue(60, 100, BREAKEVEN_AT_NEG_110), expected, abs_tol=1e-12)


def test_binomial_pvalue_matches_scipy_low_winrate():
    # Win rate below breakeven → p-value > 0.5
    expected = _scipy_binomtest(48, 100, BREAKEVEN_AT_NEG_110, alternative="greater").pvalue
    assert math.isclose(binomial_pvalue(48, 100, BREAKEVEN_AT_NEG_110), expected, abs_tol=1e-12)


def test_binomial_pvalue_zero_n_is_one():
    # No data → cannot reject null → pvalue = 1.0
    assert binomial_pvalue(0, 0, 0.5238) == 1.0


def test_binomial_pvalue_default_breakeven_is_neg110():
    expected = _scipy_binomtest(60, 100, BREAKEVEN_AT_NEG_110, alternative="greater").pvalue
    assert math.isclose(binomial_pvalue(60, 100), expected, abs_tol=1e-12)
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: collection error.

- [ ] **Step 3: Append `binomial_pvalue` to `engine/stats_utils.py`**

```python
from scipy.stats import binomtest as _binomtest


def binomial_pvalue(wins: int, n: int, breakeven: float = BREAKEVEN_AT_NEG_110) -> float:
    """One-sided exact binomial test: P(X >= wins | n, breakeven).

    Asks: "Is this observed win rate significantly better than chance against the
    breakeven required to profit at the given juice?"
    Returns 1.0 when n == 0.
    """
    if n == 0:
        return 1.0
    if wins < 0 or wins > n:
        raise ValueError(f"wins={wins} must be in [0, n={n}]")
    return _binomtest(wins, n, breakeven, alternative="greater").pvalue
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: 15 passed.

- [ ] **Step 5: Commit**

```powershell
git add engine/stats_utils.py tests/test_stats_utils.py
git commit -m "feat(stats): binomial p-value vs configurable breakeven"
```

---

## Task 5: stats_utils — Wilson CI

**Files:**
- Modify: `engine/stats_utils.py` (append)
- Modify: `tests/test_stats_utils.py` (append)

- [ ] **Step 1: Append failing tests**

```python
from engine.stats_utils import wilson_ci


def test_wilson_ci_55_of_100():
    # Hand-calculated with z=1.96:
    #   center = (55 + 1.92) / (100 + 3.8416) = 56.9208 / 103.8416 ≈ 0.54815
    #   half = 1.96 * sqrt(100*0.55*0.45 + 3.8416/4) / 103.8416 ≈ 0.09571
    # CI ≈ (0.45244, 0.64386)
    lo, hi = wilson_ci(55, 100, alpha=0.05)
    assert math.isclose(lo, 0.45244, abs_tol=1e-4)
    assert math.isclose(hi, 0.64386, abs_tol=1e-4)


def test_wilson_ci_zero_n_returns_zero_one():
    lo, hi = wilson_ci(0, 0)
    assert (lo, hi) == (0.0, 1.0)


def test_wilson_ci_all_wins_does_not_exceed_one():
    lo, hi = wilson_ci(10, 10)
    assert 0.0 < lo < 1.0
    assert hi <= 1.0


def test_wilson_ci_all_losses_does_not_go_negative():
    lo, hi = wilson_ci(0, 10)
    assert lo >= 0.0
    assert 0.0 < hi < 1.0
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: collection error.

- [ ] **Step 3: Append `wilson_ci` to `engine/stats_utils.py`**

```python
from scipy.stats import norm as _norm


def wilson_ci(wins: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a proportion.

    Preferred over the normal approximation at small n and when p_hat is near 0 or 1.
    Returns (0.0, 1.0) when n == 0 (no information).
    """
    if n == 0:
        return (0.0, 1.0)
    if wins < 0 or wins > n:
        raise ValueError(f"wins={wins} must be in [0, n={n}]")
    z = _norm.ppf(1.0 - alpha / 2.0)
    p_hat = wins / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: 19 passed.

- [ ] **Step 5: Commit**

```powershell
git add engine/stats_utils.py tests/test_stats_utils.py
git commit -m "feat(stats): Wilson score confidence interval"
```

---

## Task 6: stats_utils — Kelly fraction

**Files:**
- Modify: `engine/stats_utils.py` (append)
- Modify: `tests/test_stats_utils.py` (append)

- [ ] **Step 1: Append failing tests**

```python
from engine.stats_utils import kelly_fraction


def test_kelly_at_neg110_with_55pct_winprob():
    # f* = (0.55 * (10/11) - 0.45) / (10/11) = 0.055 exact
    assert math.isclose(kelly_fraction(0.55, 1 + 10 / 11), 0.055, abs_tol=1e-12)


def test_kelly_clamps_to_zero_when_negative_edge():
    # p=0.45 at -110 → negative EV; Kelly should clamp to 0 (no bet)
    assert kelly_fraction(0.45, 1 + 10 / 11) == 0.0


def test_kelly_at_plus_odds():
    # p=0.40 at +150 (decimal 2.5, b=1.5):
    # f* = (0.4*1.5 - 0.6) / 1.5 = 0.0 / 1.5 = 0.0 (exactly break-even, no bet)
    assert kelly_fraction(0.40, 2.5) == 0.0


def test_kelly_at_plus_odds_positive_edge():
    # p=0.45 at +150 (b=1.5):
    # f* = (0.45*1.5 - 0.55) / 1.5 = 0.125 / 1.5 ≈ 0.0833...
    assert math.isclose(kelly_fraction(0.45, 2.5), 0.125 / 1.5, abs_tol=1e-12)


def test_kelly_invalid_prob_raises():
    import pytest

    with pytest.raises(ValueError):
        kelly_fraction(-0.1, 2.0)
    with pytest.raises(ValueError):
        kelly_fraction(1.1, 2.0)
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: collection error.

- [ ] **Step 3: Append `kelly_fraction` to `engine/stats_utils.py`**

```python
def kelly_fraction(p_win: float, decimal_odds: float) -> float:
    """Optimal Kelly bet fraction.

    f* = (p * b - q) / b, where b = decimal_odds - 1, q = 1 - p.
    Clamped to >= 0 (do not place negative-EV bets).
    """
    if not 0.0 <= p_win <= 1.0:
        raise ValueError(f"p_win={p_win} must be in [0, 1]")
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal_odds={decimal_odds} must be > 1")
    b = decimal_odds - 1.0
    q = 1.0 - p_win
    f_star = (p_win * b - q) / b
    return max(0.0, f_star)
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_stats_utils.py -q
```

Expected: 24 passed.

- [ ] **Step 5: Commit**

```powershell
git add engine/stats_utils.py tests/test_stats_utils.py
git commit -m "feat(stats): Kelly fraction with negative-EV clamp"
```

---

## Task 7: ingestion/divisions.py — 32-team static lookup

**Files:**
- Create: `ingestion/divisions.py`
- Create: `tests/test_static_data.py`

- [ ] **Step 1: Write failing tests** in `tests/test_static_data.py`

```python
from ingestion.divisions import DIVISIONS, division_of, same_division


def test_divisions_has_32_teams():
    assert len(DIVISIONS) == 32


def test_divisions_has_8_divisions_with_4_teams_each():
    counts: dict[tuple[str, str], int] = {}
    for team, (conf, div) in DIVISIONS.items():
        counts[(conf, div)] = counts.get((conf, div), 0) + 1
    assert len(counts) == 8
    assert all(c == 4 for c in counts.values())


def test_division_of_known_teams():
    assert division_of("Kansas City Chiefs") == ("AFC", "West")
    assert division_of("Dallas Cowboys") == ("NFC", "East")
    assert division_of("Green Bay Packers") == ("NFC", "North")


def test_same_division_true():
    assert same_division("Kansas City Chiefs", "Denver Broncos") is True


def test_same_division_false_same_conference():
    assert same_division("Kansas City Chiefs", "Buffalo Bills") is False


def test_same_division_false_different_conference():
    assert same_division("Kansas City Chiefs", "Dallas Cowboys") is False
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_static_data.py -q
```

Expected: ImportError.

- [ ] **Step 3: Create `ingestion/divisions.py`**

```python
"""Static NFL division lookup (2002 realignment, valid 2002–present).

Teams are stored by their canonical name. Use ingestion/team_names.py to
normalize a possibly-historical name (e.g. "St. Louis Rams") to its canonical
form ("Los Angeles Rams") before looking up here.
"""

from __future__ import annotations

DIVISIONS: dict[str, tuple[str, str]] = {
    # AFC East
    "Buffalo Bills": ("AFC", "East"),
    "Miami Dolphins": ("AFC", "East"),
    "New England Patriots": ("AFC", "East"),
    "New York Jets": ("AFC", "East"),
    # AFC North
    "Baltimore Ravens": ("AFC", "North"),
    "Cincinnati Bengals": ("AFC", "North"),
    "Cleveland Browns": ("AFC", "North"),
    "Pittsburgh Steelers": ("AFC", "North"),
    # AFC South
    "Houston Texans": ("AFC", "South"),
    "Indianapolis Colts": ("AFC", "South"),
    "Jacksonville Jaguars": ("AFC", "South"),
    "Tennessee Titans": ("AFC", "South"),
    # AFC West
    "Denver Broncos": ("AFC", "West"),
    "Kansas City Chiefs": ("AFC", "West"),
    "Las Vegas Raiders": ("AFC", "West"),
    "Los Angeles Chargers": ("AFC", "West"),
    # NFC East
    "Dallas Cowboys": ("NFC", "East"),
    "New York Giants": ("NFC", "East"),
    "Philadelphia Eagles": ("NFC", "East"),
    "Washington Commanders": ("NFC", "East"),
    # NFC North
    "Chicago Bears": ("NFC", "North"),
    "Detroit Lions": ("NFC", "North"),
    "Green Bay Packers": ("NFC", "North"),
    "Minnesota Vikings": ("NFC", "North"),
    # NFC South
    "Atlanta Falcons": ("NFC", "South"),
    "Carolina Panthers": ("NFC", "South"),
    "New Orleans Saints": ("NFC", "South"),
    "Tampa Bay Buccaneers": ("NFC", "South"),
    # NFC West
    "Arizona Cardinals": ("NFC", "West"),
    "Los Angeles Rams": ("NFC", "West"),
    "San Francisco 49ers": ("NFC", "West"),
    "Seattle Seahawks": ("NFC", "West"),
}


def division_of(team: str) -> tuple[str, str]:
    """Return (conference, division) for a canonical team name."""
    return DIVISIONS[team]


def same_division(team_a: str, team_b: str) -> bool:
    """True if both canonical team names are in the same division."""
    return DIVISIONS[team_a] == DIVISIONS[team_b]
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_static_data.py -q
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/divisions.py tests/test_static_data.py
git commit -m "feat(ingestion): 32-team division lookup"
```

---

## Task 8: ingestion/team_names.py — historical → canonical mapping

**Files:**
- Create: `ingestion/team_names.py`
- Modify: `tests/test_static_data.py` (append)

- [ ] **Step 1: Append failing tests** to `tests/test_static_data.py`

```python
from ingestion.team_names import CANONICAL_TEAMS, canonicalize_team_name


def test_canonicalize_modern_name_passthrough():
    assert canonicalize_team_name("Kansas City Chiefs") == "Kansas City Chiefs"


def test_canonicalize_st_louis_rams():
    assert canonicalize_team_name("St. Louis Rams") == "Los Angeles Rams"


def test_canonicalize_san_diego_chargers():
    assert canonicalize_team_name("San Diego Chargers") == "Los Angeles Chargers"


def test_canonicalize_oakland_raiders():
    assert canonicalize_team_name("Oakland Raiders") == "Las Vegas Raiders"


def test_canonicalize_washington_redskins():
    assert canonicalize_team_name("Washington Redskins") == "Washington Commanders"


def test_canonicalize_washington_football_team():
    assert canonicalize_team_name("Washington Football Team") == "Washington Commanders"


def test_canonical_teams_match_divisions():
    from ingestion.divisions import DIVISIONS

    assert CANONICAL_TEAMS == set(DIVISIONS.keys())


def test_canonicalize_unknown_team_raises():
    import pytest

    with pytest.raises(KeyError):
        canonicalize_team_name("Cleveland Browns 1971 Edition")
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_static_data.py -q
```

Expected: ImportError.

- [ ] **Step 3: Create `ingestion/team_names.py`**

```python
"""Historical NFL team name normalization (covers 2004–2024 window).

Source CSVs (e.g. Kaggle spreadspoke_scores) record the name in use at game time.
This module maps any historical variant to the franchise's canonical 2024 name.
"""

from __future__ import annotations

# Canonical name = the team's 2024-season name. Mapping covers every variant
# seen in the 2004–2024 window plus a few obvious aliases (e.g. "LA Rams").
_NAME_MAP: dict[str, str] = {
    # AFC East
    "Buffalo Bills": "Buffalo Bills",
    "Miami Dolphins": "Miami Dolphins",
    "New England Patriots": "New England Patriots",
    "New York Jets": "New York Jets",
    # AFC North
    "Baltimore Ravens": "Baltimore Ravens",
    "Cincinnati Bengals": "Cincinnati Bengals",
    "Cleveland Browns": "Cleveland Browns",
    "Pittsburgh Steelers": "Pittsburgh Steelers",
    # AFC South
    "Houston Texans": "Houston Texans",
    "Indianapolis Colts": "Indianapolis Colts",
    "Jacksonville Jaguars": "Jacksonville Jaguars",
    "Tennessee Titans": "Tennessee Titans",
    # AFC West — Raiders moved Oakland → Las Vegas (2020); Chargers SD → LA (2017)
    "Denver Broncos": "Denver Broncos",
    "Kansas City Chiefs": "Kansas City Chiefs",
    "Las Vegas Raiders": "Las Vegas Raiders",
    "Oakland Raiders": "Las Vegas Raiders",
    "Los Angeles Chargers": "Los Angeles Chargers",
    "San Diego Chargers": "Los Angeles Chargers",
    # NFC East — Washington renamed twice (2020 → Football Team, 2022 → Commanders)
    "Dallas Cowboys": "Dallas Cowboys",
    "New York Giants": "New York Giants",
    "Philadelphia Eagles": "Philadelphia Eagles",
    "Washington Commanders": "Washington Commanders",
    "Washington Football Team": "Washington Commanders",
    "Washington Redskins": "Washington Commanders",
    # NFC North
    "Chicago Bears": "Chicago Bears",
    "Detroit Lions": "Detroit Lions",
    "Green Bay Packers": "Green Bay Packers",
    "Minnesota Vikings": "Minnesota Vikings",
    # NFC South
    "Atlanta Falcons": "Atlanta Falcons",
    "Carolina Panthers": "Carolina Panthers",
    "New Orleans Saints": "New Orleans Saints",
    "Tampa Bay Buccaneers": "Tampa Bay Buccaneers",
    # NFC West — Rams moved STL → LA (2016)
    "Arizona Cardinals": "Arizona Cardinals",
    "Los Angeles Rams": "Los Angeles Rams",
    "St. Louis Rams": "Los Angeles Rams",
    "San Francisco 49ers": "San Francisco 49ers",
    "Seattle Seahawks": "Seattle Seahawks",
}

CANONICAL_TEAMS: set[str] = set(_NAME_MAP.values())


def canonicalize_team_name(name: str) -> str:
    """Map any historical NFL team name to its canonical 2024 name.

    Raises KeyError on unknown names (callers should not silently accept
    typos or non-NFL teams).
    """
    return _NAME_MAP[name]
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_static_data.py -q
```

Expected: 14 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/team_names.py tests/test_static_data.py
git commit -m "feat(ingestion): historical team-name canonicalization"
```

---

## Task 9: ingestion/stadiums.py — stadium → dome flag

**Files:**
- Create: `ingestion/stadiums.py`
- Modify: `tests/test_static_data.py` (append)

- [ ] **Step 1: Append failing tests**

```python
from ingestion.stadiums import is_dome


def test_is_dome_known_dome():
    # State Farm Stadium (Arizona) is a retractable-roof dome
    assert is_dome("State Farm Stadium") is True
    # Mercedes-Benz Superdome (New Orleans) is a fixed dome
    assert is_dome("Mercedes-Benz Superdome") is True
    # Caesars Superdome — same building, post-2021 rename
    assert is_dome("Caesars Superdome") is True


def test_is_dome_known_outdoor():
    assert is_dome("Lambeau Field") is False
    assert is_dome("Heinz Field") is False
    assert is_dome("Arrowhead Stadium") is False


def test_is_dome_unknown_returns_false():
    # Unknown stadium → conservative default = outdoor (False)
    assert is_dome("Some Made-Up Stadium") is False
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_static_data.py -q
```

Expected: ImportError.

- [ ] **Step 3: Create `ingestion/stadiums.py`**

```python
"""Stadium dome-flag lookup.

Includes every NFL stadium used in the 2004–2024 window. Conservative default
for unknown stadiums is False (outdoor) — we'd rather mis-classify a rare
neutral-site dome as outdoor than the reverse.
"""

from __future__ import annotations

_DOME_STADIUMS: set[str] = {
    # Fixed-roof domes
    "Mercedes-Benz Superdome",
    "Caesars Superdome",
    "Ford Field",
    "Hubert H. Humphrey Metrodome",
    "U.S. Bank Stadium",
    "Edward Jones Dome",
    "RCA Dome",
    "Lucas Oil Stadium",
    "Alamodome",
    "Carrier Dome",
    "Allegiant Stadium",
    "SoFi Stadium",
    "Mercedes-Benz Stadium",
    # Retractable-roof domes (counted as domes since the league decides whether
    # to play with the roof open or closed, and for Slice 1 we only need the
    # gross indoor/outdoor distinction)
    "AT&T Stadium",
    "NRG Stadium",
    "Reliant Stadium",
    "State Farm Stadium",
    "University of Phoenix Stadium",
    "Cardinals Stadium",
    "Lucas Oil Stadium",  # already above
    "Tottenham Hotspur Stadium",
}


def is_dome(stadium: str | None) -> bool:
    """True if the stadium has a roof. Unknown / missing → False."""
    if stadium is None:
        return False
    return stadium in _DOME_STADIUMS
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_static_data.py -q
```

Expected: 17 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/stadiums.py tests/test_static_data.py
git commit -m "feat(ingestion): stadium dome-flag lookup"
```

---

## Task 10: engine/db.py — connection, schema init, query helper

**Files:**
- Create: `engine/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests** in `tests/test_db.py`

```python
import sqlite3

import pandas as pd

from engine.db import connect, fetch_df, init_schema


def test_init_schema_creates_three_tables(memory_db):
    init_schema(memory_db)
    tables = {
        row["name"]
        for row in memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert tables == {"games", "betting_lines", "team_divisions"}


def test_init_schema_is_idempotent(memory_db):
    init_schema(memory_db)
    init_schema(memory_db)  # should not raise
    tables = {
        row["name"]
        for row in memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
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
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_db.py -q
```

Expected: ImportError.

- [ ] **Step 3: Create `engine/db.py`**

```python
"""SQLite connection + schema management for the betting analytics DB."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Sequence

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
    home_spread_result TEXT CHECK (home_spread_result IN ('cover','push','loss') OR home_spread_result IS NULL),
    total_result       TEXT CHECK (total_result      IN ('over','push','under')  OR total_result      IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_betting_lines_game ON betting_lines(game_id);

CREATE TABLE IF NOT EXISTS team_divisions (
    team       TEXT PRIMARY KEY,
    conference TEXT NOT NULL,
    division   TEXT NOT NULL
);
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
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_db.py -q
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```powershell
git add engine/db.py tests/test_db.py
git commit -m "feat(db): SQLite schema + connect + fetch_df helper"
```

---

## Task 11: loader helper — `derive_spread_home_close`

**Files:**
- Create: `ingestion/loader.py` (will be appended to in subsequent tasks)
- Create: `tests/test_loader_helpers.py`

- [ ] **Step 1: Write failing test** in `tests/test_loader_helpers.py`

```python
import math

import pytest

from ingestion.loader import derive_spread_home_close


def test_home_favored():
    # Kaggle stores spread_favorite as a magnitude with a separate favorite-team id.
    # If team_favorite_id resolves to home, spread_home_close = -|spread|.
    assert derive_spread_home_close(spread_favorite=-7.0, favorite_is_home=True) == -7.0


def test_away_favored():
    # If team_favorite_id resolves to away, spread_home_close = +|spread|.
    assert derive_spread_home_close(spread_favorite=-3.5, favorite_is_home=False) == 3.5


def test_pickem_returns_zero():
    assert derive_spread_home_close(spread_favorite=0.0, favorite_is_home=True) == 0.0
    assert derive_spread_home_close(spread_favorite=0.0, favorite_is_home=False) == 0.0


def test_missing_spread_returns_none():
    assert derive_spread_home_close(spread_favorite=None, favorite_is_home=True) is None


def test_positive_input_normalized():
    # Defensive: if a row has positive spread_favorite for some reason,
    # treat its magnitude as the spread.
    assert derive_spread_home_close(spread_favorite=7.0, favorite_is_home=True) == -7.0
    assert derive_spread_home_close(spread_favorite=7.0, favorite_is_home=False) == 7.0


def test_nan_treated_as_missing():
    assert derive_spread_home_close(spread_favorite=math.nan, favorite_is_home=True) is None
```

- [ ] **Step 2: Run test, expect failure**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

Expected: ImportError (loader.py doesn't exist).

- [ ] **Step 3: Create `ingestion/loader.py` with helper**

```python
"""CSV → SQLite loader for NFL betting data.

Pure derivation helpers are exported individually for unit testing.
The end-to-end orchestrator is ``load_csv_to_db``.
"""

from __future__ import annotations

import math


def derive_spread_home_close(
    spread_favorite: float | None,
    favorite_is_home: bool,
) -> float | None:
    """Convert (magnitude, favorite-is-home) to a home-perspective signed spread.

    Output convention:
      - negative = home favored
      - positive = home underdog
      - 0        = pick'em
      - None     = data missing
    """
    if spread_favorite is None or (isinstance(spread_favorite, float) and math.isnan(spread_favorite)):
        return None
    magnitude = abs(spread_favorite)
    return -magnitude if favorite_is_home else magnitude
```

- [ ] **Step 4: Run tests, expect pass**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/loader.py tests/test_loader_helpers.py
git commit -m "feat(loader): derive home-perspective spread from Kaggle layout"
```

---

## Task 12: loader helper — `derive_ats_result`

**Files:**
- Modify: `ingestion/loader.py` (append)
- Modify: `tests/test_loader_helpers.py` (append)

- [ ] **Step 1: Append failing tests**

```python
from ingestion.loader import derive_ats_result


def test_ats_home_favored_and_covers():
    # Home -7, final 28-17 → margin +11, beats the spread → cover for home side
    assert derive_ats_result(home_score=28, away_score=17, spread_home_close=-7.0) == "cover"


def test_ats_home_favored_and_loses():
    # Home -7, final 21-20 → margin +1, fails to cover → loss
    assert derive_ats_result(home_score=21, away_score=20, spread_home_close=-7.0) == "loss"


def test_ats_home_favored_push():
    # Home -7, final 24-17 → margin +7 exactly → push
    assert derive_ats_result(home_score=24, away_score=17, spread_home_close=-7.0) == "push"


def test_ats_home_underdog_covers():
    # Home +3, final 17-20 → margin -3 ; with +3 buffer → 0 exactly → push
    assert derive_ats_result(home_score=17, away_score=20, spread_home_close=3.0) == "push"
    # Home +3, final 20-21 → margin -1 + 3 = +2 → cover
    assert derive_ats_result(home_score=20, away_score=21, spread_home_close=3.0) == "cover"


def test_ats_pickem_outright_winner():
    # Pickem (0), home wins → home covers
    assert derive_ats_result(home_score=27, away_score=20, spread_home_close=0.0) == "cover"
    # Pickem (0), home loses → loss
    assert derive_ats_result(home_score=20, away_score=27, spread_home_close=0.0) == "loss"
    # Pickem (0), tie → push
    assert derive_ats_result(home_score=20, away_score=20, spread_home_close=0.0) == "push"


def test_ats_missing_inputs_returns_none():
    assert derive_ats_result(home_score=None, away_score=20, spread_home_close=-3.0) is None
    assert derive_ats_result(home_score=20, away_score=None, spread_home_close=-3.0) is None
    assert derive_ats_result(home_score=20, away_score=20, spread_home_close=None) is None
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

- [ ] **Step 3: Append to `ingestion/loader.py`**

```python
def derive_ats_result(
    home_score: int | None,
    away_score: int | None,
    spread_home_close: float | None,
) -> str | None:
    """Compute home-side ATS result.

    Adjusts the home margin by the spread (negative = home favored).
    Returns 'cover' if adjusted > 0, 'loss' if < 0, 'push' if == 0.
    Returns None if any input is missing.
    """
    if home_score is None or away_score is None or spread_home_close is None:
        return None
    home_margin = home_score - away_score
    adjusted = home_margin + spread_home_close
    if adjusted > 0:
        return "cover"
    if adjusted < 0:
        return "loss"
    return "push"
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

Expected: 14 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/loader.py tests/test_loader_helpers.py
git commit -m "feat(loader): derive home-side ATS result"
```

---

## Task 13: loader helper — `derive_total_result`

**Files:**
- Modify: `ingestion/loader.py` (append)
- Modify: `tests/test_loader_helpers.py` (append)

- [ ] **Step 1: Append failing tests**

```python
from ingestion.loader import derive_total_result


def test_total_over():
    assert derive_total_result(home_score=28, away_score=24, total_close=45.5) == "over"


def test_total_under():
    assert derive_total_result(home_score=10, away_score=7, total_close=45.5) == "under"


def test_total_push():
    assert derive_total_result(home_score=24, away_score=21, total_close=45.0) == "push"


def test_total_missing_returns_none():
    assert derive_total_result(home_score=None, away_score=21, total_close=45.0) is None
    assert derive_total_result(home_score=21, away_score=None, total_close=45.0) is None
    assert derive_total_result(home_score=21, away_score=21, total_close=None) is None
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

- [ ] **Step 3: Append to `ingestion/loader.py`**

```python
def derive_total_result(
    home_score: int | None,
    away_score: int | None,
    total_close: float | None,
) -> str | None:
    """Compute over/under/push for the combined score vs the total line."""
    if home_score is None or away_score is None or total_close is None:
        return None
    combined = home_score + away_score
    if combined > total_close:
        return "over"
    if combined < total_close:
        return "under"
    return "push"
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

Expected: 18 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/loader.py tests/test_loader_helpers.py
git commit -m "feat(loader): derive over/under/push from total close"
```

---

## Task 14: loader helper — `parse_week`

**Files:**
- Modify: `ingestion/loader.py` (append)
- Modify: `tests/test_loader_helpers.py` (append)

- [ ] **Step 1: Append failing tests**

```python
from ingestion.loader import parse_week


def test_parse_regular_season_week():
    assert parse_week("1") == 1
    assert parse_week("18") == 18


def test_parse_playoff_strings():
    assert parse_week("Wildcard") == 100
    assert parse_week("Division") == 101
    assert parse_week("Conference") == 102
    assert parse_week("Superbowl") == 103


def test_parse_week_integer_input():
    assert parse_week(5) == 5


def test_parse_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        parse_week("Preseason")
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

- [ ] **Step 3: Append to `ingestion/loader.py`**

```python
_PLAYOFF_WEEK_MAP: dict[str, int] = {
    "Wildcard": 100,
    "Division": 101,
    "Conference": 102,
    "Superbowl": 103,
}


def parse_week(raw: str | int) -> int:
    """Map Kaggle's schedule_week values to integer weeks.

    Regular season "1"–"18" → integer; playoff strings → 100–103.
    """
    if isinstance(raw, int):
        return raw
    if raw in _PLAYOFF_WEEK_MAP:
        return _PLAYOFF_WEEK_MAP[raw]
    try:
        return int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Unknown schedule_week value: {raw!r}") from e
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

Expected: 22 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/loader.py tests/test_loader_helpers.py
git commit -m "feat(loader): parse regular-season and playoff week values"
```

---

## Task 15: loader helper — `derive_division_game_flag`

**Files:**
- Modify: `ingestion/loader.py` (append)
- Modify: `tests/test_loader_helpers.py` (append)

- [ ] **Step 1: Append failing tests**

```python
from ingestion.loader import derive_division_game_flag


def test_same_division_returns_one():
    assert derive_division_game_flag("Kansas City Chiefs", "Denver Broncos") == 1


def test_same_conference_different_division_returns_zero():
    assert derive_division_game_flag("Kansas City Chiefs", "Buffalo Bills") == 0


def test_different_conference_returns_zero():
    assert derive_division_game_flag("Kansas City Chiefs", "Dallas Cowboys") == 0


def test_historical_name_inputs_handled():
    # Caller is expected to canonicalize names BEFORE this helper.
    # We document that requirement by asserting that the canonical-name
    # version works and an unknown name raises.
    import pytest

    with pytest.raises(KeyError):
        derive_division_game_flag("Oakland Raiders", "Kansas City Chiefs")
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

- [ ] **Step 3: Append to `ingestion/loader.py`**

```python
from ingestion.divisions import same_division


def derive_division_game_flag(home_team: str, away_team: str) -> int:
    """1 if the two teams are in the same division, else 0.

    Both inputs must be canonical team names. Caller is responsible for
    running them through ingestion.team_names.canonicalize_team_name first.
    """
    return 1 if same_division(home_team, away_team) else 0
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

Expected: 26 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/loader.py tests/test_loader_helpers.py
git commit -m "feat(loader): division-game flag derivation"
```

---

## Task 16: loader helper — `derive_primetime_flag`

**Files:**
- Modify: `ingestion/loader.py` (append)
- Modify: `tests/test_loader_helpers.py` (append)

The Kaggle dataset doesn't directly expose primetime/SNF/MNF/TNF. We use a coarse heuristic: a regular-season game on Mon/Thu/Sat/Sun-night is treated as primetime. The Kaggle file's `schedule_date` is a date (no time), so we approximate by day-of-week only. Refinement (with actual kickoff times) is deferred to Slice 2.

- [ ] **Step 1: Append failing tests**

```python
from datetime import date

from ingestion.loader import derive_primetime_flag


def test_monday_is_primetime():
    # 2024-10-14 was a Monday (Saints @ Chiefs MNF)
    assert derive_primetime_flag(date(2024, 10, 14), playoff=False) == 1


def test_thursday_is_primetime():
    # 2024-09-05 was a Thursday (Ravens @ Chiefs season-opener TNF)
    assert derive_primetime_flag(date(2024, 9, 5), playoff=False) == 1


def test_saturday_is_primetime():
    # Late-season Saturday games are typically primetime broadcasts
    assert derive_primetime_flag(date(2024, 12, 21), playoff=False) == 1


def test_regular_sunday_not_primetime():
    # A regular Sunday could be 1pm or SNF; without time info we conservatively
    # call it not primetime. Note: this under-counts SNF games.
    assert derive_primetime_flag(date(2024, 10, 13), playoff=False) == 0


def test_playoff_game_never_primetime_flag():
    # Playoff games are flagged by playoff_flag, not primetime_flag,
    # to avoid double-counting in later analyses.
    assert derive_primetime_flag(date(2024, 1, 13), playoff=True) == 0
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

- [ ] **Step 3: Append to `ingestion/loader.py`**

```python
from datetime import date as _date

_PRIMETIME_WEEKDAYS: set[int] = {0, 3, 5}  # Monday=0, Thursday=3, Saturday=5


def derive_primetime_flag(game_date: _date, playoff: bool) -> int:
    """Coarse primetime heuristic for the regular season.

    Monday, Thursday, and Saturday regular-season games are treated as primetime.
    Sunday Night Football is NOT captured by this heuristic (no time data in
    the source CSV) and is therefore under-counted. Slice 2 refines this.

    Playoff games always return 0 here; downstream code should branch on
    playoff_flag rather than primetime_flag for playoff analyses.
    """
    if playoff:
        return 0
    return 1 if game_date.weekday() in _PRIMETIME_WEEKDAYS else 0
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_loader_helpers.py -q
```

Expected: 31 passed.

- [ ] **Step 5: Commit**

```powershell
git add ingestion/loader.py tests/test_loader_helpers.py
git commit -m "feat(loader): coarse primetime heuristic (day-of-week)"
```

---

## Task 17: Build `tests/fixtures/games_5.csv`

**Files:**
- Create: `tests/fixtures/games_5.csv`

This is a hand-built fixture that exercises every derivation. The column names match `spreadspoke_scores.csv` exactly so the loader code can be reused unchanged on the real dataset.

- [ ] **Step 1: Create the fixture file**

```powershell
New-Item -ItemType Directory tests/fixtures -Force
```

Then create `tests/fixtures/games_5.csv` with this exact content (CRLF or LF both fine; pandas handles both):

```csv
schedule_date,schedule_season,schedule_week,schedule_playoff,team_home,team_away,team_favorite_id,score_home,score_away,spread_favorite,over_under_line,weather_temperature,weather_wind_mph,weather_humidity,stadium,stadium_neutral
2024-10-14,2024,6,FALSE,Kansas City Chiefs,New Orleans Saints,KAN,26,13,-6.0,46.0,72,5,55,Arrowhead Stadium,FALSE
2024-12-29,2024,17,FALSE,Green Bay Packers,Minnesota Vikings,MIN,25,27,-3.0,40.0,18,12,60,Lambeau Field,FALSE
2024-09-15,2024,2,FALSE,Houston Texans,Chicago Bears,PICK,19,13,0.0,42.5,,,,NRG Stadium,FALSE
2024-01-13,2023,Wildcard,TRUE,Buffalo Bills,Pittsburgh Steelers,BUF,31,17,-9.5,38.0,28,18,70,Highmark Stadium,FALSE
2024-09-08,2024,1,FALSE,Atlanta Falcons,Pittsburgh Steelers,PIT,10,18,-3.0,,71,3,50,Mercedes-Benz Stadium,FALSE
```

Game-by-game design:
1. **Row 1** — Mon 2024-10-14, Chiefs (home, -6) beat Saints 26-13. Margin +13, spread -6 → covers. Total 46, combined 39 → under. Division flag = 0 (KC vs NO). Primetime = 1 (Monday). Playoff = 0. Stadium not in dome list → dome 0.
2. **Row 2** — Sun 2024-12-29, Packers vs Vikings (NFC North division game). Vikings favored -3 → home (GB) spread = +3. Final 25-27, home margin -2; +3 buffer → +1 → cover for home (Packers cover the +3). Total 40, combined 52 → over. Primetime = 0 (Sunday).
3. **Row 3** — pick'em, missing weather columns (blank cells). Home (HOU) wins 19-13 → home covers pick'em. Total 42.5, combined 32 → under. NRG Stadium → dome = 1.
4. **Row 4** — Wildcard playoff. Buffalo -9.5 over Pittsburgh. Final 31-17 margin +14 → covers. Total 38, combined 48 → over. playoff_flag = 1, primetime_flag = 0 (per heuristic, playoff always 0 even if Saturday).
5. **Row 5** — Atlanta (home) vs Pittsburgh (away). Pit favored -3 → home spread = +3. Final 10-18 margin -8 + 3 = -5 → loss. Total = NULL → total_result NULL. Mercedes-Benz Stadium → dome 1.

(Note: schedule_week column is intentionally string-typed in row 4 to test playoff parsing.)

- [ ] **Step 2: Commit**

```powershell
git add tests/fixtures/games_5.csv
git commit -m "test(loader): 5-game fixture exercising every derivation"
```

---

## Task 18: loader — `load_csv_to_db` end-to-end

**Files:**
- Modify: `ingestion/loader.py` (append orchestrator + CLI)
- Create: `tests/test_loader.py`

- [ ] **Step 1: Write failing integration tests** in `tests/test_loader.py`

```python
from pathlib import Path

import pytest

from engine.db import connect, init_schema
from ingestion.loader import LoadReport, load_csv_to_db


@pytest.fixture
def loaded_db(tmp_db_path, fixtures_dir):
    report = load_csv_to_db(
        csv_path=fixtures_dir / "games_5.csv",
        db_path=tmp_db_path,
        season_min=2023,  # widen to include the wildcard game (season 2023, played Jan 2024)
        season_max=2024,
    )
    conn = connect(tmp_db_path)
    try:
        yield conn, report
    finally:
        conn.close()


def test_load_report_counts(loaded_db):
    _, report = loaded_db
    assert isinstance(report, LoadReport)
    assert report.rows_read == 5
    assert report.rows_inserted == 5


def test_load_creates_all_5_games(loaded_db):
    conn, _ = loaded_db
    n = conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()["c"]
    assert n == 5


def test_load_creates_all_5_lines(loaded_db):
    conn, _ = loaded_db
    n = conn.execute("SELECT COUNT(*) AS c FROM betting_lines").fetchone()["c"]
    assert n == 5


def test_row1_chiefs_saints(loaded_db):
    conn, _ = loaded_db
    g = conn.execute(
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
    conn, _ = loaded_db
    g = conn.execute(
        "SELECT g.*, b.spread_home_close, b.home_spread_result, b.total_result "
        "FROM games g JOIN betting_lines b ON b.game_id = g.game_id "
        "WHERE g.home_team = 'Green Bay Packers' AND g.season = 2024"
    ).fetchone()
    assert g["division_game_flag"] == 1
    assert g["spread_home_close"] == 3.0
    assert g["home_spread_result"] == "cover"  # 25-27 margin -2 + 3 = +1
    assert g["total_result"] == "over"  # combined 52 > 40


def test_row3_pickem_with_missing_weather(loaded_db):
    conn, _ = loaded_db
    g = conn.execute(
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
    conn, _ = loaded_db
    g = conn.execute(
        "SELECT * FROM games WHERE home_team = 'Buffalo Bills' AND season = 2023"
    ).fetchone()
    assert g["week"] == 100
    assert g["playoff_flag"] == 1
    assert g["primetime_flag"] == 0  # playoff override


def test_row5_missing_total_handled(loaded_db):
    conn, _ = loaded_db
    g = conn.execute(
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
        # betting_lines uses INSERT OR REPLACE keyed on (game_id) — also exactly 5
        assert n_lines == 5
    finally:
        conn.close()


def test_load_respects_season_filter(tmp_db_path, fixtures_dir):
    # season_min=2024 should drop the wildcard row (which is season 2023).
    report = load_csv_to_db(
        fixtures_dir / "games_5.csv", tmp_db_path, season_min=2024, season_max=2024
    )
    assert report.rows_inserted == 4
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_loader.py -q
```

Expected: collection error / ImportError on `LoadReport` and `load_csv_to_db`.

- [ ] **Step 3: Append orchestrator + CLI to `ingestion/loader.py`**

The new code references derivation helpers + `team_names` + `stadiums` + `db` defined in prior tasks. Add the following at the bottom of `ingestion/loader.py`:

```python
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from engine.db import connect, init_schema
from ingestion.stadiums import is_dome
from ingestion.team_names import canonicalize_team_name

_log = logging.getLogger(__name__)


@dataclass
class LoadReport:
    rows_read: int = 0
    rows_inserted: int = 0
    rows_skipped_missing_score: int = 0
    rows_skipped_missing_spread: int = 0
    by_season: dict[int, int] = field(default_factory=dict)


def _resolve_favorite_is_home(team_favorite_id: str, home_team: str) -> bool:
    """Kaggle's team_favorite_id is a short code (e.g. 'KAN', 'GB') or 'PICK'.

    We map by checking whether the favorite code's expansion equals the home team
    (after canonicalization). The mapping is small and embedded here to keep the
    loader self-contained for Slice 1.
    """
    # Minimal short-code → canonical team name map.
    # Source: Kaggle dataset codes (column team_favorite_id in spreadspoke_scores).
    code_to_team = {
        "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
        "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
        "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
        "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
        "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
        "KC": "Kansas City Chiefs", "KAN": "Kansas City Chiefs",
        "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
        "LV": "Las Vegas Raiders", "LVR": "Las Vegas Raiders",
        "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings", "NE": "New England Patriots",
        "NO": "New Orleans Saints", "NYG": "New York Giants", "NYJ": "New York Jets",
        "OAK": "Las Vegas Raiders",
        "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
        "SD": "Los Angeles Chargers", "SDG": "Los Angeles Chargers",
        "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "SFO": "San Francisco 49ers",
        "STL": "Los Angeles Rams",
        "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
        "WAS": "Washington Commanders",
    }
    if team_favorite_id == "PICK":
        return False  # pick'em — sign doesn't matter, magnitude is 0
    if team_favorite_id not in code_to_team:
        raise ValueError(f"Unknown team_favorite_id: {team_favorite_id!r}")
    return code_to_team[team_favorite_id] == home_team


def _to_int_or_none(x) -> int | None:
    if x is None or pd.isna(x):
        return None
    return int(x)


def _to_float_or_none(x) -> float | None:
    if x is None or pd.isna(x):
        return None
    return float(x)


def _make_game_id(season: int, week: int, away: str, home: str) -> str:
    away_slug = away.replace(" ", "_").replace(".", "")
    home_slug = home.replace(" ", "_").replace(".", "")
    return f"{season}_{week}_{away_slug}_{home_slug}"


def load_csv_to_db(
    csv_path: str | Path,
    db_path: str | Path,
    season_min: int = 2004,
    season_max: int = 2024,
) -> LoadReport:
    """Read the Kaggle spreadspoke_scores CSV, derive Slice-1 fields, write to SQLite.

    Idempotent: re-running with the same CSV produces the same DB state.
    """
    csv_path = Path(csv_path)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    report = LoadReport(rows_read=len(df))

    # Season filter
    df = df[(df["schedule_season"] >= season_min) & (df["schedule_season"] <= season_max)].copy()

    conn = connect(db_path)
    try:
        init_schema(conn)
        for _, row in df.iterrows():
            season = int(row["schedule_season"])
            week = parse_week(row["schedule_week"])
            game_date = pd.to_datetime(row["schedule_date"]).date()
            home = canonicalize_team_name(row["team_home"])
            away = canonicalize_team_name(row["team_away"])
            home_score = _to_int_or_none(row["score_home"])
            away_score = _to_int_or_none(row["score_away"])

            spread_favorite = _to_float_or_none(row["spread_favorite"])
            favorite_is_home = _resolve_favorite_is_home(str(row["team_favorite_id"]), home)
            spread_home_close = derive_spread_home_close(spread_favorite, favorite_is_home)

            total_close = _to_float_or_none(row["over_under_line"])
            home_spread_result = derive_ats_result(home_score, away_score, spread_home_close)
            total_result = derive_total_result(home_score, away_score, total_close)

            playoff = str(row["schedule_playoff"]).upper() == "TRUE"
            primetime = derive_primetime_flag(game_date, playoff)
            division_flag = derive_division_game_flag(home, away)
            stadium = row["stadium"] if pd.notna(row["stadium"]) else None
            dome = 1 if is_dome(stadium) else 0

            game_id = _make_game_id(season, week, away, home)

            conn.execute(
                """INSERT OR REPLACE INTO games(
                    game_id, season, week, game_date, home_team, away_team,
                    home_score, away_score, stadium, dome_flag,
                    weather_temp, weather_wind, weather_humidity,
                    primetime_flag, playoff_flag, division_game_flag
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    game_id, season, week, game_date.isoformat(), home, away,
                    home_score, away_score, stadium, dome,
                    _to_int_or_none(row.get("weather_temperature")),
                    _to_int_or_none(row.get("weather_wind_mph")),
                    _to_int_or_none(row.get("weather_humidity")),
                    primetime, int(playoff), division_flag,
                ),
            )
            # Idempotent line insert: delete prior line(s) for this game, then insert one.
            conn.execute("DELETE FROM betting_lines WHERE game_id = ?", (game_id,))
            conn.execute(
                """INSERT INTO betting_lines(
                    game_id, spread_home_close, total_close,
                    home_spread_result, total_result
                ) VALUES (?,?,?,?,?)""",
                (game_id, spread_home_close, total_close, home_spread_result, total_result),
            )

            report.rows_inserted += 1
            report.by_season[season] = report.by_season.get(season, 0) + 1
            if home_score is None or away_score is None:
                report.rows_skipped_missing_score += 1
            if spread_home_close is None:
                report.rows_skipped_missing_spread += 1

        conn.commit()
    finally:
        conn.close()

    _log.info(
        "Loaded %d rows from %s into %s (seasons %d-%d)",
        report.rows_inserted, csv_path, db_path, season_min, season_max,
    )
    return report


def _main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if len(argv) < 2:
        print("usage: python -m ingestion.loader <path/to/spreadspoke_scores.csv>", file=sys.stderr)
        return 2
    csv_path = Path(argv[1])
    db_path = Path("data/db/nfl_betting.sqlite")
    report = load_csv_to_db(csv_path, db_path)
    print(f"Read:      {report.rows_read}")
    print(f"Inserted:  {report.rows_inserted}")
    print(f"By season: {dict(sorted(report.by_season.items()))}")
    print(f"Missing scores  in inserted rows: {report.rows_skipped_missing_score}")
    print(f"Missing spreads in inserted rows: {report.rows_skipped_missing_spread}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_loader.py -q
```

Expected: 9 passed.

- [ ] **Step 5: Run the full test suite to confirm nothing else broke**

```powershell
uv run pytest -q
```

Expected: all tests green (sum of every prior task's tests + these 9).

- [ ] **Step 6: Commit**

```powershell
git add ingestion/loader.py tests/test_loader.py
git commit -m "feat(loader): end-to-end CSV → SQLite orchestrator + CLI"
```

---

## Task 19: ATS — `bucket_spread`

**Files:**
- Create: `engine/ats.py`
- Create: `tests/test_ats.py`

- [ ] **Step 1: Write failing tests** in `tests/test_ats.py`

```python
import pytest

from engine.ats import bucket_spread


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
        (-0.5, "pickem"),
        (0.0, "pickem"),
        (0.5, "pickem"),
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
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_ats.py -q
```

Expected: ImportError.

- [ ] **Step 3: Create `engine/ats.py`**

```python
"""ATS-by-spread-bucket analysis.

Buckets the home-perspective signed spread into the 11 categories defined in
the Slice 1 spec, then aggregates wins / losses / pushes / metrics per bucket.
"""

from __future__ import annotations


# Bucket order is the order they will appear in the final report (favorites → dogs).
BUCKET_ORDER: list[str] = [
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


def bucket_spread(spread_home_close: float | None) -> str | None:
    """Bucket the home-perspective spread.

    Pick'em covers (-0.5, 0, 0.5). Favorites and underdogs partition the rest.
    """
    if spread_home_close is None:
        return None
    s = spread_home_close
    if -0.5 <= s <= 0.5:
        return "pickem"
    if s < 0:
        m = -s  # magnitude when home is favored
        if m >= 14.5:
            return "home_fav_14.5+"
        if m >= 10.5:
            return "home_fav_10.5_14"
        if m >= 7.5:
            return "home_fav_7.5_10"
        if m >= 3.5:
            return "home_fav_3.5_7"
        return "home_fav_1_3"
    # s > 0.5 → home is the dog
    if s >= 14.5:
        return "home_dog_14.5+"
    if s >= 10.5:
        return "home_dog_10.5_14"
    if s >= 7.5:
        return "home_dog_7.5_10"
    if s >= 3.5:
        return "home_dog_3.5_7"
    return "home_dog_1_3"
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_ats.py -q
```

Expected: 24 passed (23 parametrize cases + 1 None test).

- [ ] **Step 5: Commit**

```powershell
git add engine/ats.py tests/test_ats.py
git commit -m "feat(ats): spread-bucket classifier"
```

---

## Task 20: ATS — `compute_bucket_metrics`

**Files:**
- Modify: `engine/ats.py` (append)
- Modify: `tests/test_ats.py` (append)

- [ ] **Step 1: Append failing tests**

```python
import math

from engine.ats import BucketMetrics, compute_bucket_metrics


def test_metrics_basic_case():
    # 60 covers, 40 losses, 0 pushes → win_rate = 0.60
    m = compute_bucket_metrics(bucket="home_fav_3.5_7", covers=60, losses=40, pushes=0)
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
    m = compute_bucket_metrics(bucket="pickem", covers=10, losses=10, pushes=5)
    assert m.n == 25
    # win_rate excludes pushes from denominator
    assert math.isclose(m.win_rate, 0.5)
    # push_rate uses total
    assert math.isclose(m.push_rate, 0.2)


def test_metrics_insufficient_sample_flag_below_50():
    m = compute_bucket_metrics(bucket="home_fav_14.5+", covers=20, losses=20, pushes=0)
    assert m.insufficient_sample is True
    m2 = compute_bucket_metrics(bucket="home_fav_14.5+", covers=30, losses=20, pushes=0)
    # 30+20 = 50, threshold is wins+losses < 50 → exactly 50 is NOT insufficient
    assert m2.insufficient_sample is False


def test_metrics_zero_data():
    m = compute_bucket_metrics(bucket="pickem", covers=0, losses=0, pushes=0)
    assert m.n == 0
    assert m.win_rate == 0.0
    assert m.push_rate == 0.0
    assert m.p_value == 1.0
    assert m.ci_low == 0.0
    assert m.ci_high == 1.0
    assert m.insufficient_sample is True
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_ats.py -q
```

Expected: ImportError.

- [ ] **Step 3: Append to `engine/ats.py`**

```python
from dataclasses import dataclass

from engine.stats_utils import (
    BREAKEVEN_AT_NEG_110,
    binomial_pvalue,
    roi,
    wilson_ci,
)


@dataclass
class BucketMetrics:
    bucket: str
    n: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    push_rate: float
    roi_neg110: float
    roi_neg105: float
    p_value: float
    ci_low: float
    ci_high: float
    insufficient_sample: bool


def compute_bucket_metrics(
    bucket: str,
    covers: int,
    losses: int,
    pushes: int,
) -> BucketMetrics:
    """Aggregate cover/loss/push counts into a fully-specified metrics row."""
    n = covers + losses + pushes
    decided = covers + losses
    if decided == 0:
        win_rate = 0.0
    else:
        win_rate = covers / decided
    push_rate = (pushes / n) if n > 0 else 0.0

    p = binomial_pvalue(covers, decided, BREAKEVEN_AT_NEG_110)
    lo, hi = wilson_ci(covers, decided)
    return BucketMetrics(
        bucket=bucket,
        n=n,
        wins=covers,
        losses=losses,
        pushes=pushes,
        win_rate=win_rate,
        push_rate=push_rate,
        roi_neg110=roi(covers, losses, pushes, -110),
        roi_neg105=roi(covers, losses, pushes, -105),
        p_value=p,
        ci_low=lo,
        ci_high=hi,
        insufficient_sample=decided < 50,
    )
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_ats.py -q
```

Expected: 28 passed.

- [ ] **Step 5: Commit**

```powershell
git add engine/ats.py tests/test_ats.py
git commit -m "feat(ats): per-bucket metric aggregation"
```

---

## Task 21: Build `tests/fixtures/games_20_ats.csv`

**Files:**
- Create: `tests/fixtures/games_20_ats.csv`

This 20-game fixture is engineered so each populated bucket has known counts. Designed so the test in Task 22 can hand-verify the aggregate.

Bucket plan (covers/losses/pushes):
- `home_fav_3.5_7`: 3 games → 2 covers, 1 loss
- `home_fav_1_3`: 3 games → 1 cover, 1 loss, 1 push
- `pickem`: 2 games → 1 cover, 1 loss
- `home_dog_1_3`: 3 games → 2 covers, 1 loss
- `home_dog_3.5_7`: 3 games → 1 cover, 2 losses
- `home_dog_7.5_10`: 6 games → 3 covers, 3 losses

All "home favorites" rows have `team_favorite_id` = the home team code; all "home dog" rows have `team_favorite_id` = the away team code; pick'em rows use `PICK`.

- [ ] **Step 1: Create the fixture file**

Create `tests/fixtures/games_20_ats.csv` with this exact content:

```csv
schedule_date,schedule_season,schedule_week,schedule_playoff,team_home,team_away,team_favorite_id,score_home,score_away,spread_favorite,over_under_line,weather_temperature,weather_wind_mph,weather_humidity,stadium,stadium_neutral
2024-09-08,2024,1,FALSE,Buffalo Bills,Miami Dolphins,BUF,30,10,-5.0,45.0,72,5,55,Highmark Stadium,FALSE
2024-09-15,2024,2,FALSE,Kansas City Chiefs,Cincinnati Bengals,KAN,27,17,-4.0,46.0,75,3,60,Arrowhead Stadium,FALSE
2024-09-22,2024,3,FALSE,Dallas Cowboys,Baltimore Ravens,DAL,17,28,-6.0,47.0,72,4,40,AT&T Stadium,FALSE
2024-09-29,2024,4,FALSE,Detroit Lions,Seattle Seahawks,DET,24,21,-3.0,48.0,72,0,50,Ford Field,FALSE
2024-10-06,2024,5,FALSE,Philadelphia Eagles,Cleveland Browns,PHI,20,17,-2.5,42.0,68,6,45,Lincoln Financial Field,FALSE
2024-10-13,2024,6,FALSE,Green Bay Packers,Arizona Cardinals,GB,17,14,-2.0,44.0,55,8,60,Lambeau Field,FALSE
2024-10-20,2024,7,FALSE,Atlanta Falcons,Carolina Panthers,PICK,28,7,0.0,43.0,70,3,55,Mercedes-Benz Stadium,FALSE
2024-10-27,2024,8,FALSE,Tampa Bay Buccaneers,New Orleans Saints,PICK,17,24,0.0,45.0,80,4,65,Raymond James Stadium,FALSE
2024-11-03,2024,9,FALSE,Chicago Bears,Detroit Lions,DET,21,18,-2.5,42.0,50,10,55,Soldier Field,FALSE
2024-11-10,2024,10,FALSE,Houston Texans,Indianapolis Colts,IND,24,20,-1.5,46.0,72,0,50,NRG Stadium,FALSE
2024-11-17,2024,11,FALSE,Miami Dolphins,Buffalo Bills,BUF,21,28,-3.0,44.0,72,8,75,Hard Rock Stadium,FALSE
2024-11-24,2024,12,FALSE,Cleveland Browns,Pittsburgh Steelers,PIT,10,16,-5.5,38.0,40,12,55,Cleveland Browns Stadium,FALSE
2024-12-01,2024,13,FALSE,Minnesota Vikings,Green Bay Packers,GB,17,30,-3.5,44.0,68,0,50,U.S. Bank Stadium,FALSE
2024-12-08,2024,14,FALSE,Carolina Panthers,Philadelphia Eagles,PHI,21,17,-6.0,42.0,55,10,60,Bank of America Stadium,FALSE
2024-09-08,2024,1,FALSE,New York Jets,San Francisco 49ers,SF,14,32,-8.0,41.0,72,4,50,MetLife Stadium,FALSE
2024-09-15,2024,2,FALSE,Las Vegas Raiders,Baltimore Ravens,BAL,10,26,-9.5,43.0,72,0,40,Allegiant Stadium,FALSE
2024-09-22,2024,3,FALSE,Jacksonville Jaguars,Buffalo Bills,BUF,28,30,-9.0,46.0,85,6,75,EverBank Stadium,FALSE
2024-09-29,2024,4,FALSE,Tennessee Titans,Houston Texans,HOU,24,21,-7.5,42.0,72,8,55,Nissan Stadium,FALSE
2024-10-06,2024,5,FALSE,Denver Broncos,Kansas City Chiefs,KC,17,21,-8.0,44.0,55,12,40,Empower Field at Mile High,FALSE
2024-10-13,2024,6,FALSE,Washington Commanders,Philadelphia Eagles,PHI,30,40,-8.5,48.0,68,5,50,FedExField,FALSE
```

Game-by-game ATS verification:

| # | Home / Away | Fav | Sprd (home POV) | Score | Margin + sprd | Bucket | Result |
|---|---|---|---|---|---|---|---|
| 1 | BUF / MIA | BUF | -5.0 | 30-10 | +20-5 = +15 | home_fav_3.5_7 | cover |
| 2 | KC / CIN | KC | -4.0 | 27-17 | +10-4 = +6 | home_fav_3.5_7 | cover |
| 3 | DAL / BAL | DAL | -6.0 | 17-28 | -11-6 = -17 | home_fav_3.5_7 | loss |
| 4 | DET / SEA | DET | -3.0 | 24-21 | +3-3 = 0 | home_fav_1_3 | push |
| 5 | PHI / CLE | PHI | -2.5 | 20-17 | +3-2.5 = +0.5 | home_fav_1_3 | cover |
| 6 | GB / ARI | GB | -2.0 | 17-14 | +3-2 = +1 | home_fav_1_3 | cover |
| 7 | ATL / CAR | PICK | 0 | 28-7 | +21 | pickem | cover |
| 8 | TB / NO | PICK | 0 | 17-24 | -7 | pickem | loss |
| 9 | CHI / DET | DET | +2.5 (home dog) | 21-18 | +3+2.5 = +5.5 | home_dog_1_3 | cover |
| 10 | HOU / IND | IND | +1.5 (home dog) | 24-20 | +4+1.5 = +5.5 | home_dog_1_3 | cover |
| 11 | MIA / BUF | BUF | +3.0 (home dog) | 21-28 | -7+3 = -4 | home_dog_1_3 | loss |
| 12 | CLE / PIT | PIT | +5.5 (home dog) | 10-16 | -6+5.5 = -0.5 | home_dog_3.5_7 | loss |
| 13 | MIN / GB | GB | +3.5 (home dog) | 17-30 | -13+3.5 = -9.5 | home_dog_3.5_7 | loss |
| 14 | CAR / PHI | PHI | +6.0 (home dog) | 21-17 | +4+6 = +10 | home_dog_3.5_7 | cover |
| 15 | NYJ / SF | SF | +8.0 (home dog) | 14-32 | -18+8 = -10 | home_dog_7.5_10 | loss |
| 16 | LV / BAL | BAL | +9.5 (home dog) | 10-26 | -16+9.5 = -6.5 | home_dog_7.5_10 | loss |
| 17 | JAX / BUF | BUF | +9.0 (home dog) | 28-30 | -2+9 = +7 | home_dog_7.5_10 | cover |
| 18 | TEN / HOU | HOU | +7.5 (home dog) | 24-21 | +3+7.5 = +10.5 | home_dog_7.5_10 | cover |
| 19 | DEN / KC | KC | +8.0 (home dog) | 17-21 | -4+8 = +4 | home_dog_7.5_10 | cover |
| 20 | WAS / PHI | PHI | +8.5 (home dog) | 30-40 | -10+8.5 = -1.5 | home_dog_7.5_10 | loss |

Expected bucket aggregates:
- `home_fav_3.5_7`: 3 games → 2 covers, 1 loss, 0 pushes
- `home_fav_1_3`: 3 games → 2 covers, 0 losses, 1 push
- `pickem`: 2 games → 1 cover, 1 loss, 0 pushes
- `home_dog_1_3`: 3 games → 2 covers, 1 loss, 0 pushes
- `home_dog_3.5_7`: 3 games → 1 cover, 2 losses, 0 pushes
- `home_dog_7.5_10`: 6 games → 3 covers, 3 losses, 0 pushes
- Other buckets: 0

(Note: the bucket-5 spec original had a different count — the table above is the **authoritative** expected output for the test.)

- [ ] **Step 2: Commit**

```powershell
git add tests/fixtures/games_20_ats.csv
git commit -m "test(ats): 20-game ATS-bucket fixture with hand-verified results"
```

---

## Task 22: ATS — `ats_by_spread_bucket` end-to-end

**Files:**
- Modify: `engine/ats.py` (append)
- Modify: `tests/test_ats.py` (append)

- [ ] **Step 1: Append failing test**

```python
from pathlib import Path

from engine.ats import ats_by_spread_bucket
from engine.db import connect
from ingestion.loader import load_csv_to_db


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
```

- [ ] **Step 2: Run test, expect failure**

```powershell
uv run pytest tests/test_ats.py -q
```

Expected: ImportError on `ats_by_spread_bucket` and `BucketMetrics.by_season`.

- [ ] **Step 3: Extend `BucketMetrics` and add `ats_by_spread_bucket` to `engine/ats.py`**

First, modify `BucketMetrics` to add `by_season`. Replace the existing dataclass with:

```python
@dataclass
class BucketMetrics:
    bucket: str
    n: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    push_rate: float
    roi_neg110: float
    roi_neg105: float
    p_value: float
    ci_low: float
    ci_high: float
    insufficient_sample: bool
    by_season: dict[int, float] = field(default_factory=dict)
```

Then update `compute_bucket_metrics` to accept an optional `by_season` argument:

```python
def compute_bucket_metrics(
    bucket: str,
    covers: int,
    losses: int,
    pushes: int,
    by_season: dict[int, float] | None = None,
) -> BucketMetrics:
    n = covers + losses + pushes
    decided = covers + losses
    win_rate = (covers / decided) if decided > 0 else 0.0
    push_rate = (pushes / n) if n > 0 else 0.0
    p = binomial_pvalue(covers, decided, BREAKEVEN_AT_NEG_110)
    lo, hi = wilson_ci(covers, decided)
    return BucketMetrics(
        bucket=bucket,
        n=n,
        wins=covers,
        losses=losses,
        pushes=pushes,
        win_rate=win_rate,
        push_rate=push_rate,
        roi_neg110=roi(covers, losses, pushes, -110),
        roi_neg105=roi(covers, losses, pushes, -105),
        p_value=p,
        ci_low=lo,
        ci_high=hi,
        insufficient_sample=decided < 50,
        by_season=by_season or {},
    )
```

Update the existing `from dataclasses import dataclass` line at the top of `engine/ats.py` to `from dataclasses import dataclass, field`. Add `import sqlite3` and `import pandas as pd` to the imports block. Then append the new container + function:

```python
@dataclass
class AtsReport:
    rows: list[BucketMetrics]


def ats_by_spread_bucket(conn: sqlite3.Connection) -> AtsReport:
    """Aggregate ATS results into the 11 home-spread buckets.

    Joins games and betting_lines on game_id, drops rows where
    spread_home_close or home_spread_result is NULL.
    """
    df = pd.read_sql_query(
        """
        SELECT g.season, b.spread_home_close, b.home_spread_result
        FROM games g
        JOIN betting_lines b ON b.game_id = g.game_id
        WHERE b.spread_home_close IS NOT NULL
          AND b.home_spread_result IS NOT NULL
        """,
        conn,
    )
    df["bucket"] = df["spread_home_close"].apply(bucket_spread)

    rows: list[BucketMetrics] = []
    for bucket in BUCKET_ORDER:
        sub = df[df["bucket"] == bucket]
        covers = int((sub["home_spread_result"] == "cover").sum())
        losses = int((sub["home_spread_result"] == "loss").sum())
        pushes = int((sub["home_spread_result"] == "push").sum())

        by_season: dict[int, float] = {}
        if len(sub) > 0:
            for season, group in sub.groupby("season"):
                c = int((group["home_spread_result"] == "cover").sum())
                l = int((group["home_spread_result"] == "loss").sum())
                decided = c + l
                if decided > 0:
                    by_season[int(season)] = c / decided

        rows.append(compute_bucket_metrics(bucket, covers, losses, pushes, by_season))

    return AtsReport(rows=rows)
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_ats.py -q
```

Expected: 30 passed (28 prior + 2 new).

- [ ] **Step 5: Run the full suite**

```powershell
uv run pytest -q
```

Expected: all tests still green.

- [ ] **Step 6: Commit**

```powershell
git add engine/ats.py tests/test_ats.py
git commit -m "feat(ats): ats_by_spread_bucket aggregator with by-season trends"
```

---

## Task 23: ATS — CLI entry + CSV output + disclaimer

**Files:**
- Modify: `engine/ats.py` (append CLI + formatter)
- Modify: `tests/test_ats.py` (append CLI test)

- [ ] **Step 1: Append failing test**

```python
import subprocess
import sys


def test_ats_csv_output_is_written(tmp_db_path, fixtures_dir, tmp_path, monkeypatch):
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


def test_ats_stdout_includes_disclaimer(capsys, tmp_db_path, fixtures_dir, tmp_path, monkeypatch):
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
```

- [ ] **Step 2: Run tests, expect failure**

```powershell
uv run pytest tests/test_ats.py -q
```

Expected: ImportError on `_main`.

- [ ] **Step 3: Append CLI + formatting to `engine/ats.py`**

```python
import csv
import sys
from pathlib import Path

from tabulate import tabulate

DISCLAIMER = (
    "Past performance does not guarantee future results. "
    "This tool is for informational purposes only. Gamble responsibly."
)


def format_report(report: AtsReport) -> str:
    """Format the report as a tabulated table for stdout."""
    headers = [
        "bucket", "n", "W", "L", "P",
        "win%", "push%", "ROI -110", "ROI -105",
        "p-value", "CI low", "CI high", "low_n?",
    ]
    rows = []
    for r in report.rows:
        rows.append([
            r.bucket, r.n, r.wins, r.losses, r.pushes,
            f"{r.win_rate:.4f}" if r.n else "—",
            f"{r.push_rate:.4f}" if r.n else "—",
            f"{r.roi_neg110:+.4f}" if r.n else "—",
            f"{r.roi_neg105:+.4f}" if r.n else "—",
            f"{r.p_value:.4f}",
            f"{r.ci_low:.4f}",
            f"{r.ci_high:.4f}",
            "*" if r.insufficient_sample else "",
        ])
    return tabulate(rows, headers=headers, tablefmt="github")


def write_csv(report: AtsReport, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        # Disclaimer comment line at the top of the CSV
        f.write(f"# {DISCLAIMER}\n")
        writer = csv.writer(f)
        writer.writerow([
            "bucket", "n", "wins", "losses", "pushes",
            "win_rate", "push_rate", "roi_neg110", "roi_neg105",
            "p_value", "ci_low", "ci_high", "insufficient_sample",
            "by_season",
        ])
        for r in report.rows:
            writer.writerow([
                r.bucket, r.n, r.wins, r.losses, r.pushes,
                f"{r.win_rate:.6f}",
                f"{r.push_rate:.6f}",
                f"{r.roi_neg110:.6f}",
                f"{r.roi_neg105:.6f}",
                f"{r.p_value:.6f}",
                f"{r.ci_low:.6f}",
                f"{r.ci_high:.6f}",
                int(r.insufficient_sample),
                ";".join(f"{s}:{w:.4f}" for s, w in sorted(r.by_season.items())),
            ])


def _main(_argv: list[str] | None = None) -> int:
    db_path = Path("data/db/nfl_betting.sqlite")
    out_csv = Path("data/processed/ats_by_bucket.csv")
    if not db_path.exists():
        print(
            f"Database not found at {db_path}. "
            "Run `python -m ingestion.loader data/raw/spreadspoke_scores.csv` first.",
            file=sys.stderr,
        )
        return 2

    conn = connect(db_path)  # type: ignore[name-defined]
    try:
        report = ats_by_spread_bucket(conn)
    finally:
        conn.close()

    print(format_report(report))
    print()
    print(DISCLAIMER)

    write_csv(report, out_csv)
    print(f"\nCSV written to {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
```

Add the missing `connect` import at the top of `engine/ats.py`:

```python
from engine.db import connect
```

- [ ] **Step 4: Run tests**

```powershell
uv run pytest tests/test_ats.py -q
```

Expected: 32 passed.

- [ ] **Step 5: Run full suite + ruff**

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: tests green, ruff clean (or only auto-fixable nits; run `uv run ruff check --fix .` if so).

- [ ] **Step 6: Commit**

```powershell
git add engine/ats.py tests/test_ats.py
git commit -m "feat(ats): CLI entry, tabulated stdout, CSV output, disclaimer"
```

---

## Task 24: README + smoke test against real Kaggle data

**Files:**
- Modify: `README.md`

This is the acceptance step. The user manually places `spreadspoke_scores.csv` in `data/raw/` and runs the two CLI commands. The plan walks through verifying the output.

- [ ] **Step 1: Expand `README.md`** with verification instructions

```markdown
# NFL Betting Analytics

> Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

Slice 1 of the NFL Sports Betting Analytics Engine. Loads historical NFL games + closing lines from a Kaggle CSV into SQLite and produces an ATS-by-spread-bucket report with full statistical rigor (n, win rate, ROI at -110/-105, p-value vs the 52.38% breakeven, Wilson 95% CI, and by-season trend).

See `docs/superpowers/specs/2026-05-26-nfl-betting-slice1-design.md` for the design.

## Setup

```powershell
uv sync
```

## Run tests

```powershell
uv run pytest -q
```

All tests should pass with zero failures.

## Lint

```powershell
uv run ruff check .
```

## Ingest data

1. Download `spreadspoke_scores.csv` from the Kaggle "NFL Scores and Betting Data" dataset.
2. Place it at `data/raw/spreadspoke_scores.csv`.
3. Run:

   ```powershell
   uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv
   ```

   This populates `data/db/nfl_betting.sqlite`. Default season filter: 2004–2024. Re-running with the same CSV is idempotent.

## Generate the ATS report

```powershell
uv run python -m engine.ats
```

The command prints a per-bucket table to stdout and writes `data/processed/ats_by_bucket.csv`. The disclaimer appears in both outputs.

## Slice 1 scope

This slice covers ingestion, schema, statistics utilities, and the proof-of-concept ATS-by-spread-bucket analysis. Totals, moneyline, composites, regression, dashboards, and live odds are deferred to later slices.
```

- [ ] **Step 2: Run the real-data smoke test**

(The user has to manually place the CSV at `data/raw/spreadspoke_scores.csv`. This step is the engineer / user verifying end-to-end.)

```powershell
uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv
```

Expected:
- A line per season showing inserted counts.
- ~5,000–5,500 rows inserted across 2004–2024 (regular + playoffs).
- No tracebacks.

```powershell
uv run python -m engine.ats
```

Expected:
- Tabulated table with 11 rows (one per bucket). Several buckets should show n in the hundreds to thousands. The very-large-spread buckets (-14.5+, +14.5+) may show n < 50 and be flagged with `*`.
- Trailing disclaimer line.
- `data/processed/ats_by_bucket.csv` created.

- [ ] **Step 3: Final commit**

```powershell
git add README.md
git commit -m "docs(readme): document Slice 1 setup, ingestion, and report commands"
```

- [ ] **Step 4: Tag the Slice 1 milestone**

```powershell
git tag -a slice1-complete -m "Slice 1: ingestion + schema + stats utils + ATS-by-bucket"
```

---

## Slice 1 — Definition of Done checklist

- [ ] `uv sync` succeeds on a fresh checkout.
- [ ] `uv run pytest -q` reports all tests passing.
- [ ] `uv run ruff check .` is clean.
- [ ] With `spreadspoke_scores.csv` at `data/raw/`, the loader command populates the DB and prints a load report.
- [ ] Re-running the loader is a no-op (idempotent — game and line counts unchanged).
- [ ] `python -m engine.ats` prints a populated table and writes `data/processed/ats_by_bucket.csv`, both with the disclaimer.
- [ ] README documents all four user-facing commands.
- [ ] The design doc is committed and referenced from the README.
