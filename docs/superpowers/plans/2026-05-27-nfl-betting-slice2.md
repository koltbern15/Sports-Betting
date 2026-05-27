# NFL Betting Analytics — Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Slice 1's ATS analysis to two more bet markets — totals (over/under) and moneyline (with prices derived from closing spreads) — while extracting shared bucket-analysis machinery into a reusable module.

**Architecture:** Refactor `engine/ats.py` to pull its dataclass, table-formatting, and CSV-writing helpers into a new `engine/bucket_analysis.py`. Then add two new analysis modules (`engine/totals.py`, `engine/moneyline.py`) that follow the same shape. No schema changes. Pure-function discipline preserved (derivation, bucketing, and ROI all testable in isolation). Hand-verified-fixture tests for both aggregators.

**Tech Stack:** Python 3.11+, `uv`, `pandas`, `numpy`, `scipy`, `tabulate`, `pytest`, `ruff`, SQLite (stdlib). Same stack as Slice 1.

**Spec:** `docs/superpowers/specs/2026-05-27-nfl-betting-slice2-design.md`

---

## Conventions used throughout this plan

- **All commands run from the project root** `C:\Users\ktber\projects\sports-betting`.
- **All commands assume PowerShell.** Forward slashes in `uv` / `pytest` arguments are fine.
- **Every task ends with a commit.** Conventional Commits (`feat:`, `refactor:`, `test:`, `chore:`, `docs:`).
- **Run `uv run pytest -q` after each task** to confirm previously-green tests are still green.
- **Reference values used in tests (computed with `SIGMA=13.86`, `OVERROUND=1.04762`):**

  | spread_home | ML_home | ML_away |
  |---|---|---|
  |  0.0 | -110 | -110 |
  | -3.0 | -159 | +130 |
  | -7.0 | -265 | +211 |
  | -14.0 | -762 | +511 |
  | +3.0 | +130 | -159 |

---

## File-level decomposition

| File | Responsibility | Lifecycle in Slice 2 |
|---|---|---|
| `engine/bucket_analysis.py` | Shared `BucketMetrics`, `compute_metrics`, `format_table`, `write_csv`, `DISCLAIMER` | **NEW** (T1) |
| `engine/ats.py` | ATS bucket fn + aggregator + CLI; imports shared helpers | **MODIFY** (T1) |
| `engine/stats_utils.py` | Existing + `dollar_weighted_roi()` | **MODIFY** (T2) |
| `engine/moneyline.py` | `derive_ml_from_spread`, `bucket_ml`, `moneyline_by_odds_bucket`, CLI | **NEW** (T3, T4, T9, T11) |
| `engine/totals.py` | `bucket_total`, `totals_by_line_bucket`, CLI | **NEW** (T5, T7, T10) |
| `tests/test_bucket_analysis.py` | smoke tests for shared helpers | **NEW** (T1) |
| `tests/test_stats_utils.py` | extend with `dollar_weighted_roi` tests | **MODIFY** (T2) |
| `tests/test_ats.py` | unchanged behavior, import paths may shift | **MODIFY** (T1) |
| `tests/test_moneyline.py` | tests for derive_ml_from_spread, bucket_ml, aggregator | **NEW** (T3, T4, T9) |
| `tests/test_totals.py` | tests for bucket_total, aggregator | **NEW** (T5, T7) |
| `tests/fixtures/totals_20.csv` | 20-game hand-built fixture | **NEW** (T6) |
| `tests/fixtures/moneyline_20.csv` | 20-game hand-built fixture | **NEW** (T8) |
| `README.md` | document new commands + ML derivation caveat | **MODIFY** (T12) |

---

## Task 1: Refactor — extract `engine/bucket_analysis.py`

**Files:**
- Create: `engine/bucket_analysis.py`
- Create: `tests/test_bucket_analysis.py`
- Modify: `engine/ats.py` (move helpers out, add imports)
- Modify (if needed): `tests/test_ats.py` (only if imports reference moved names directly)

Purpose: extract the shared dataclass and reporting helpers so `totals.py` and `moneyline.py` can reuse them. Behavior must not change — all 119 existing tests must remain green.

- [ ] **Step 1: Create `engine/bucket_analysis.py` with the extracted code**

```python
"""Shared bucket-analysis machinery used by ATS, totals, and moneyline modules.

Owns the BucketMetrics dataclass, the metrics-computation helper, the table
formatter, the CSV writer, and the disclaimer. All three analysis modules
delegate display/serialization to this module so output stays consistent.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from tabulate import tabulate

from engine.stats_utils import (
    BREAKEVEN_AT_NEG_110,
    binomial_pvalue,
    dollar_weighted_roi,
    roi,
    wilson_ci,
)

INSUFFICIENT_SAMPLE_THRESHOLD = 50

DISCLAIMER = (
    "Past performance does not guarantee future results. "
    "This tool is for informational purposes only. Gamble responsibly."
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
    by_season: dict[int, float] = field(default_factory=dict)


def compute_metrics(
    bucket: str,
    wins: int,
    losses: int,
    pushes: int,
    by_season: dict[int, float] | None = None,
    *,
    payouts: list[float] | None = None,
) -> BucketMetrics:
    """Aggregate win/loss/push counts into a fully-specified metrics row.

    If `payouts` is supplied, both ROI columns use dollar_weighted_roi(payouts)
    instead of fixed -110/-105 ROI from the win count. The two columns will
    then be identical.
    """
    n = wins + losses + pushes
    decided = wins + losses
    win_rate = (wins / decided) if decided > 0 else 0.0
    push_rate = (pushes / n) if n > 0 else 0.0
    p = binomial_pvalue(wins, decided, BREAKEVEN_AT_NEG_110)
    lo, hi = wilson_ci(wins, decided)
    if payouts is not None:
        roi_110 = dollar_weighted_roi(payouts)
        roi_105 = roi_110
    else:
        roi_110 = roi(wins, losses, pushes, -110)
        roi_105 = roi(wins, losses, pushes, -105)
    return BucketMetrics(
        bucket=bucket,
        n=n,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=win_rate,
        push_rate=push_rate,
        roi_neg110=roi_110,
        roi_neg105=roi_105,
        p_value=p,
        ci_low=lo,
        ci_high=hi,
        insufficient_sample=decided < INSUFFICIENT_SAMPLE_THRESHOLD,
        by_season=by_season or {},
    )


def format_table(rows: list[BucketMetrics]) -> str:
    """Render BucketMetrics rows as a GitHub-flavored tabulate table."""
    headers = [
        "bucket", "n", "W", "L", "P",
        "win%", "push%", "ROI -110", "ROI -105",
        "p-value", "CI low", "CI high", "low_n?",
    ]
    out_rows = []
    for r in rows:
        out_rows.append([
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
    return tabulate(out_rows, headers=headers, tablefmt="github")


def write_csv(rows: list[BucketMetrics], out_path: Path) -> None:
    """Write BucketMetrics rows to a CSV. Adds a disclaimer comment as line 1."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        f.write(f"# {DISCLAIMER}\n")
        writer = csv.writer(f)
        writer.writerow([
            "bucket", "n", "wins", "losses", "pushes",
            "win_rate", "push_rate", "roi_neg110", "roi_neg105",
            "p_value", "ci_low", "ci_high", "insufficient_sample",
            "by_season",
        ])
        for r in rows:
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
```

NOTE: `dollar_weighted_roi` is imported from `engine.stats_utils` but is added in Task 2. T1 won't pass tests until T2 is also done. We commit them sequentially in this order so T1's import is satisfied immediately when T2 lands.

- [ ] **Step 2: Slim down `engine/ats.py`**

Replace its full contents with this (BUCKET_ORDER, bucket_spread, AtsReport, ats_by_spread_bucket, _main remain; BucketMetrics, compute_bucket_metrics, DISCLAIMER, format_report, write_csv all delegated to `bucket_analysis`):

```python
"""ATS-by-spread-bucket analysis.

Buckets the home-perspective signed spread into the 11 categories defined in
the Slice 1 spec, then aggregates wins / losses / pushes / metrics per bucket.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from engine.bucket_analysis import (
    DISCLAIMER,
    BucketMetrics,
    compute_metrics,
    format_table,
    write_csv,
)
from engine.db import connect

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
        m = -s
        if m >= 14.5:
            return "home_fav_14.5+"
        if m >= 10.5:
            return "home_fav_10.5_14"
        if m >= 7.5:
            return "home_fav_7.5_10"
        if m >= 3.5:
            return "home_fav_3.5_7"
        return "home_fav_1_3"
    if s >= 14.5:
        return "home_dog_14.5+"
    if s >= 10.5:
        return "home_dog_10.5_14"
    if s >= 7.5:
        return "home_dog_7.5_10"
    if s >= 3.5:
        return "home_dog_3.5_7"
    return "home_dog_1_3"


@dataclass
class AtsReport:
    rows: list[BucketMetrics]


def ats_by_spread_bucket(conn: sqlite3.Connection) -> AtsReport:
    """Aggregate ATS results into the 11 home-spread buckets."""
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
                losses_ = int((group["home_spread_result"] == "loss").sum())
                decided = c + losses_
                if decided > 0:
                    by_season[int(season)] = c / decided

        rows.append(compute_metrics(bucket, covers, losses, pushes, by_season))

    return AtsReport(rows=rows)


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

    conn = connect(db_path)
    try:
        report = ats_by_spread_bucket(conn)
    finally:
        conn.close()

    print(format_table(report.rows))
    print()
    print(DISCLAIMER)

    write_csv(report.rows, out_csv)
    print(f"\nCSV written to {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
```

- [ ] **Step 3: Audit `tests/test_ats.py` for moved symbols**

Run:

```powershell
uv run python -c "import ast, sys; tree=ast.parse(open('tests/test_ats.py').read()); print('\n'.join({n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}))"
```

Expected: list of modules tests import from. If any test imports `BucketMetrics`, `compute_bucket_metrics`, `format_report`, `write_csv`, or `DISCLAIMER` from `engine.ats`, change the import to `from engine.bucket_analysis import ...` and rename `compute_bucket_metrics` → `compute_metrics` and `format_report(report)` → `format_table(report.rows)` where used.

If no imports of those names exist, no change is needed in this step.

- [ ] **Step 4: Create `tests/test_bucket_analysis.py` with smoke tests**

```python
"""Smoke tests for the shared bucket-analysis helpers.

These exist to catch regressions in the extracted machinery independent of
any one consumer module.
"""

from __future__ import annotations

from pathlib import Path

from engine.bucket_analysis import (
    DISCLAIMER,
    BucketMetrics,
    compute_metrics,
    format_table,
    write_csv,
)


def test_compute_metrics_basic_no_payouts():
    m = compute_metrics("x", wins=10, losses=8, pushes=2)
    assert m.bucket == "x"
    assert m.n == 20
    assert m.wins == 10
    assert m.losses == 8
    assert m.pushes == 2
    assert m.win_rate == 10 / 18
    assert m.push_rate == 2 / 20
    assert m.roi_neg110 != m.roi_neg105  # different juices → different ROI
    assert 0.0 <= m.ci_low <= m.ci_high <= 1.0


def test_compute_metrics_with_payouts_uses_dollar_weighted_roi():
    payouts = [1.30, -1.0, 1.30, -1.0]  # 2 wins at +130, 2 losses
    m = compute_metrics("x", wins=2, losses=2, pushes=0, payouts=payouts)
    # dollar_weighted_roi == sum(payouts)/len = (1.30 + -1 + 1.30 + -1) / 4 = 0.15
    assert m.roi_neg110 == 0.15
    assert m.roi_neg105 == 0.15


def test_compute_metrics_insufficient_sample_threshold():
    below = compute_metrics("x", wins=20, losses=20, pushes=0)  # decided=40 < 50
    above = compute_metrics("x", wins=30, losses=20, pushes=0)  # decided=50
    assert below.insufficient_sample is True
    assert above.insufficient_sample is False


def test_format_table_renders_header_and_low_n_marker():
    rows = [
        compute_metrics("a", 30, 30, 0),       # not low_n
        compute_metrics("b", 5, 5, 0),         # low_n → "*"
    ]
    out = format_table(rows)
    assert "bucket" in out and "ROI -110" in out
    assert "*" in out  # low-n marker present
    assert "a" in out and "b" in out


def test_write_csv_writes_disclaimer_then_rows(tmp_path: Path):
    rows = [compute_metrics("a", 10, 8, 2)]
    out = tmp_path / "out.csv"
    write_csv(rows, out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith(f"# {DISCLAIMER}")
    assert "bucket,n,wins" in text  # header row present
    assert "a,20,10,8,2" in text   # data row present


def test_bucket_metrics_dataclass_default_by_season_is_empty_dict():
    m = BucketMetrics(
        bucket="x", n=0, wins=0, losses=0, pushes=0,
        win_rate=0.0, push_rate=0.0,
        roi_neg110=0.0, roi_neg105=0.0,
        p_value=1.0, ci_low=0.0, ci_high=1.0,
        insufficient_sample=True,
    )
    assert m.by_season == {}
```

- [ ] **Step 5: Run tests — they will FAIL because Task 2 (`dollar_weighted_roi`) hasn't shipped yet**

```powershell
uv run pytest -q
```

Expected: `ImportError: cannot import name 'dollar_weighted_roi' from 'engine.stats_utils'` in the new `bucket_analysis` module. **Move directly to Task 2 to satisfy the import, then return here for verification.**

- [ ] **Step 6 (AFTER T2 lands): Re-run tests**

```powershell
uv run pytest -q
```

Expected: all 119 prior tests + 6 new `test_bucket_analysis` tests = **125 passing**. No failures.

- [ ] **Step 7: Lint**

```powershell
uv run ruff check .
```

Expected: clean.

- [ ] **Step 8: Commit (after both T1 and T2 changes are staged in T2's commit; T1's edits will be part of T2's commit because they cannot exist independently)**

This task's git activity is folded into Task 2's commit. **No separate commit for T1.**

---

## Task 2: `stats_utils.dollar_weighted_roi`

**Files:**
- Modify: `engine/stats_utils.py` (append `dollar_weighted_roi`)
- Modify: `tests/test_stats_utils.py` (append tests)

- [ ] **Step 1: Append failing tests to `tests/test_stats_utils.py`**

```python
# === dollar_weighted_roi ===

def test_dollar_weighted_roi_empty_returns_zero():
    from engine.stats_utils import dollar_weighted_roi
    assert dollar_weighted_roi([]) == 0.0


def test_dollar_weighted_roi_all_wins_at_fixed_price():
    from engine.stats_utils import dollar_weighted_roi
    # 4 wins at +100 → payout +1.0 each → ROI = 1.0
    assert dollar_weighted_roi([1.0, 1.0, 1.0, 1.0]) == 1.0


def test_dollar_weighted_roi_all_losses():
    from engine.stats_utils import dollar_weighted_roi
    assert dollar_weighted_roi([-1.0, -1.0, -1.0]) == -1.0


def test_dollar_weighted_roi_mixed_with_pushes():
    from engine.stats_utils import dollar_weighted_roi
    # win at -110 (pays 100/110 ≈ 0.909), loss (-1), push (0), win at +130 (pays 1.30)
    payouts = [0.909, -1.0, 0.0, 1.30]
    assert dollar_weighted_roi(payouts) == sum(payouts) / 4
```

- [ ] **Step 2: Run the tests, confirm they fail**

```powershell
uv run pytest tests/test_stats_utils.py -k dollar_weighted_roi -v
```

Expected: `ImportError` or `AttributeError` for `dollar_weighted_roi`.

- [ ] **Step 3: Append `dollar_weighted_roi` to `engine/stats_utils.py`**

```python
def dollar_weighted_roi(payouts: list[float]) -> float:
    """ROI per unit stake given a list of per-bet net profits.

    Each payout is the net PnL of one unit-staked bet:
      +N for a winning bet that pays N units profit (e.g. 0.909 at -110, 1.30 at +130)
      -1.0 for a losing bet
      0.0 for a push
    Returns 0.0 if `payouts` is empty.
    """
    if not payouts:
        return 0.0
    return sum(payouts) / len(payouts)
```

- [ ] **Step 4: Run the four new tests, confirm they pass**

```powershell
uv run pytest tests/test_stats_utils.py -k dollar_weighted_roi -v
```

Expected: 4 passed.

- [ ] **Step 5: Run the full suite, confirm everything is green**

```powershell
uv run pytest -q
```

Expected: **125 passed** (119 prior + 4 stats_utils + 6 bucket_analysis = 129 — recount: 119 + 4 = 123 in suite, plus the 6 new bucket_analysis tests = 129. Adjust if exact count differs by 1-2 due to parametrized cases.).

- [ ] **Step 6: Lint**

```powershell
uv run ruff check .
```

Expected: clean.

- [ ] **Step 7: Commit (T1 + T2 together)**

```powershell
git add engine/stats_utils.py engine/bucket_analysis.py engine/ats.py tests/test_stats_utils.py tests/test_bucket_analysis.py
git commit -m "refactor(engine): extract bucket_analysis module + add dollar_weighted_roi

Pulled BucketMetrics, compute_metrics, format_table, write_csv, and DISCLAIMER
out of engine/ats.py into engine/bucket_analysis.py so the upcoming totals and
moneyline modules can share them. Added engine.stats_utils.dollar_weighted_roi
for variable-payout markets (moneyline). Behavior of the ATS module is
unchanged; all prior tests still pass."
```

---

## Task 3: `engine.moneyline.derive_ml_from_spread`

**Files:**
- Create: `engine/moneyline.py`
- Create: `tests/test_moneyline.py`

- [ ] **Step 1: Create `tests/test_moneyline.py` with failing tests**

```python
"""Tests for engine.moneyline."""

from __future__ import annotations

import math

import pytest

from engine.moneyline import derive_ml_from_spread


@pytest.mark.parametrize(
    "spread,expected_home,expected_away",
    [
        ( 0.0, -110, -110),
        (-3.0, -159, +130),
        (-7.0, -265, +211),
        (-14.0, -762, +511),
        ( 3.0, +130, -159),
    ],
)
def test_derive_ml_from_spread_reference_values(spread, expected_home, expected_away):
    ml_home, ml_away = derive_ml_from_spread(spread)
    assert abs(ml_home - expected_home) <= 2, f"home: expected {expected_home}, got {ml_home}"
    assert abs(ml_away - expected_away) <= 2, f"away: expected {expected_away}, got {ml_away}"


def test_derive_ml_from_spread_none_returns_none():
    assert derive_ml_from_spread(None) is None


def test_derive_ml_from_spread_symmetric_around_zero():
    # ML for spread -X should mirror ML for spread +X (home/away swap)
    a_home, a_away = derive_ml_from_spread(-5.0)
    b_home, b_away = derive_ml_from_spread(+5.0)
    assert a_home == b_away
    assert a_away == b_home


def test_derive_ml_from_spread_nan_returns_none():
    assert derive_ml_from_spread(float("nan")) is None
```

- [ ] **Step 2: Run tests, confirm they fail (ImportError)**

```powershell
uv run pytest tests/test_moneyline.py -v
```

Expected: `ImportError: cannot import name 'derive_ml_from_spread' from 'engine.moneyline'`.

- [ ] **Step 3: Create `engine/moneyline.py` with the function**

```python
"""Moneyline-by-odds-bucket analysis (prices derived from closing spreads).

The Kaggle dataset has no historical sportsbook moneyline prices, so we derive
them from the closing spread via the standard normal-CDF model of NFL margins
plus a -110/-110-equivalent vig. All output clearly labels these as derived.
"""

from __future__ import annotations

import math

NFL_MARGIN_SIGMA: float = 13.86   # Burke / AdvancedNFL stats consensus
TARGET_OVERROUND: float = 1.04762  # matches -110/-110 implied probabilities


def _prob_to_american(p: float) -> int:
    """Convert an implied probability (0,1) to integer American odds (banker rounding)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"probability must be in (0,1), got {p}")
    if p >= 0.5:
        return round(-100.0 * p / (1.0 - p))
    return round(100.0 * (1.0 - p) / p)


def derive_ml_from_spread(spread_home_close: float | None) -> tuple[int, int] | None:
    """Convert a closing home-perspective spread to derived (home_ml, away_ml) American odds.

    Math:
      P_home_no_vig = Phi(-spread / sigma)   where Phi is the standard normal CDF
      P_*_vig       = P_*_no_vig * 1.04762   (proportional vig)
      ML            = American odds equivalent of P_*_vig
    Returns None if input is None or NaN.
    """
    if spread_home_close is None:
        return None
    if isinstance(spread_home_close, float) and math.isnan(spread_home_close):
        return None
    p_home_nv = 0.5 * (1.0 + math.erf(-spread_home_close / (NFL_MARGIN_SIGMA * math.sqrt(2.0))))
    p_away_nv = 1.0 - p_home_nv
    p_home_vig = p_home_nv * TARGET_OVERROUND
    p_away_vig = p_away_nv * TARGET_OVERROUND
    return (_prob_to_american(p_home_vig), _prob_to_american(p_away_vig))
```

- [ ] **Step 4: Run tests, confirm they pass**

```powershell
uv run pytest tests/test_moneyline.py -v
```

Expected: 8 passed (5 parametrized + 3 standalone).

- [ ] **Step 5: Run full suite + lint**

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: full suite green, ruff clean.

- [ ] **Step 6: Commit**

```powershell
git add engine/moneyline.py tests/test_moneyline.py
git commit -m "feat(moneyline): derive_ml_from_spread via normal-CDF + vig"
```

---

## Task 4: `engine.moneyline.bucket_ml`

**Files:**
- Modify: `engine/moneyline.py` (add `BUCKET_ORDER_ML` + `bucket_ml`)
- Modify: `tests/test_moneyline.py` (append tests)

- [ ] **Step 1: Append failing tests to `tests/test_moneyline.py`**

```python
from engine.moneyline import BUCKET_ORDER_ML, bucket_ml


@pytest.mark.parametrize(
    "ml,expected",
    [
        (-400, "ml_heavy_fav"),
        (-300, "ml_heavy_fav"),      # boundary: <= -300 → heavy
        (-299, "ml_big_fav"),
        (-250, "ml_big_fav"),
        (-249, "ml_mid_fav"),
        (-180, "ml_mid_fav"),
        (-179, "ml_small_fav"),
        (-130, "ml_small_fav"),
        (-129, "ml_slight_fav"),
        (-110, "ml_slight_fav"),
        (-109, "ml_pickem"),
        (+100, "ml_pickem"),
        (+109, "ml_pickem"),
        (+110, "ml_slight_dog"),
        (+129, "ml_slight_dog"),
        (+130, "ml_small_dog"),
        (+179, "ml_small_dog"),
        (+180, "ml_mid_dog"),
        (+249, "ml_mid_dog"),
        (+250, "ml_big_dog"),
        (+299, "ml_big_dog"),
        (+300, "ml_heavy_dog"),
        (+500, "ml_heavy_dog"),
    ],
)
def test_bucket_ml_classification(ml, expected):
    assert bucket_ml(ml) == expected


def test_bucket_ml_none_returns_none():
    assert bucket_ml(None) is None


def test_bucket_order_ml_has_11_unique_buckets():
    assert len(BUCKET_ORDER_ML) == 11
    assert len(set(BUCKET_ORDER_ML)) == 11
```

- [ ] **Step 2: Run, confirm fail**

```powershell
uv run pytest tests/test_moneyline.py -k bucket_ml -v
```

Expected: `ImportError`.

- [ ] **Step 3: Append `BUCKET_ORDER_ML` and `bucket_ml` to `engine/moneyline.py`**

```python
BUCKET_ORDER_ML: list[str] = [
    "ml_heavy_fav",
    "ml_big_fav",
    "ml_mid_fav",
    "ml_small_fav",
    "ml_slight_fav",
    "ml_pickem",
    "ml_slight_dog",
    "ml_small_dog",
    "ml_mid_dog",
    "ml_big_dog",
    "ml_heavy_dog",
]


def bucket_ml(ml_price: int | None) -> str | None:
    """Bucket an American moneyline price into one of 11 categories.

    Favorites carry negative odds; underdogs positive. Pickem covers -109..+109.
    """
    if ml_price is None:
        return None
    if ml_price <= -300:
        return "ml_heavy_fav"
    if ml_price <= -250:
        return "ml_big_fav"
    if ml_price <= -180:
        return "ml_mid_fav"
    if ml_price <= -130:
        return "ml_small_fav"
    if ml_price <= -110:
        return "ml_slight_fav"
    if ml_price < +110:
        return "ml_pickem"
    if ml_price < +130:
        return "ml_slight_dog"
    if ml_price < +180:
        return "ml_small_dog"
    if ml_price < +250:
        return "ml_mid_dog"
    if ml_price < +300:
        return "ml_big_dog"
    return "ml_heavy_dog"
```

- [ ] **Step 4: Run tests, confirm pass**

```powershell
uv run pytest tests/test_moneyline.py -v
```

Expected: 8 + 23 parametrized + 2 = 33 passed (counts approximate).

- [ ] **Step 5: Lint + full suite**

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: green, clean.

- [ ] **Step 6: Commit**

```powershell
git add engine/moneyline.py tests/test_moneyline.py
git commit -m "feat(moneyline): bucket_ml classifies American odds into 11 buckets"
```

---

## Task 5: `engine.totals.bucket_total`

**Files:**
- Create: `engine/totals.py`
- Create: `tests/test_totals.py`

- [ ] **Step 1: Create `tests/test_totals.py` with failing tests**

```python
"""Tests for engine.totals."""

from __future__ import annotations

import pytest

from engine.totals import BUCKET_ORDER_TOTALS, bucket_total


@pytest.mark.parametrize(
    "total,expected",
    [
        (35.0, "total_le_39_5"),
        (39.5, "total_le_39_5"),       # boundary inclusive on upper end
        (40.0, "total_40_42_5"),
        (42.5, "total_40_42_5"),
        (43.0, "total_43_45_5"),
        (45.5, "total_43_45_5"),
        (46.0, "total_46_48_5"),
        (48.5, "total_46_48_5"),
        (49.0, "total_49_51_5"),
        (51.5, "total_49_51_5"),
        (52.0, "total_ge_52"),
        (60.0, "total_ge_52"),
    ],
)
def test_bucket_total_classification(total, expected):
    assert bucket_total(total) == expected


def test_bucket_total_none_returns_none():
    assert bucket_total(None) is None


def test_bucket_order_totals_has_6_unique_buckets():
    assert len(BUCKET_ORDER_TOTALS) == 6
    assert len(set(BUCKET_ORDER_TOTALS)) == 6
```

- [ ] **Step 2: Run, confirm fail (ImportError)**

```powershell
uv run pytest tests/test_totals.py -v
```

- [ ] **Step 3: Create `engine/totals.py` with the bucket function**

```python
"""Totals-by-line-bucket analysis."""

from __future__ import annotations

BUCKET_ORDER_TOTALS: list[str] = [
    "total_le_39_5",
    "total_40_42_5",
    "total_43_45_5",
    "total_46_48_5",
    "total_49_51_5",
    "total_ge_52",
]


def bucket_total(total_line: float | None) -> str | None:
    """Bucket the closing total line into 6 categories (low → high)."""
    if total_line is None:
        return None
    t = total_line
    if t <= 39.5:
        return "total_le_39_5"
    if t <= 42.5:
        return "total_40_42_5"
    if t <= 45.5:
        return "total_43_45_5"
    if t <= 48.5:
        return "total_46_48_5"
    if t <= 51.5:
        return "total_49_51_5"
    return "total_ge_52"
```

- [ ] **Step 4: Run, confirm pass**

```powershell
uv run pytest tests/test_totals.py -v
```

Expected: 14 passed (12 parametrized + 2 standalone).

- [ ] **Step 5: Full suite + lint**

```powershell
uv run pytest -q
uv run ruff check .
```

- [ ] **Step 6: Commit**

```powershell
git add engine/totals.py tests/test_totals.py
git commit -m "feat(totals): bucket_total classifies closing total line into 6 buckets"
```

---

## Task 6: `tests/fixtures/totals_20.csv` — hand-built fixture

**Files:**
- Create: `tests/fixtures/totals_20.csv`

Goal: 20 games whose `over_under_line` values span all 6 totals buckets. Per-bucket distribution chosen so the aggregator test in T7 has unambiguous expected counts. All games are regular season 2023 to keep `schedule_playoff` simple.

**Per-bucket plan (hand-verified):**

| Bucket | Total line | n | over wins | under wins | pushes |
|---|---|---|---|---|---|
| `total_le_39_5`  | 38.0 | 2 | 1 | 1 | 0 |
| `total_40_42_5`  | 41.0 | 3 | 2 | 1 | 0 |
| `total_43_45_5`  | 44.0 | 4 | 3 | 1 | 0 |
| `total_46_48_5`  | 47.0 | 4 | 2 | 1 | 1 (combined total exactly hits 47) |
| `total_49_51_5`  | 50.0 | 4 | 2 | 2 | 0 |
| `total_ge_52`    | 53.0 | 3 | 1 | 2 | 0 |

Total: 20 games, 11 overs, 8 unders, 1 push.

- [ ] **Step 1: Create `tests/fixtures/totals_20.csv`**

Header columns must match the Slice 1 loader's expectations exactly.

```csv
schedule_date,schedule_season,schedule_week,schedule_playoff,team_home,team_away,team_favorite_id,score_home,score_away,spread_favorite,over_under_line,weather_temperature,weather_wind_mph,weather_humidity,stadium,stadium_neutral
2023-09-10,2023,1,FALSE,Buffalo Bills,Miami Dolphins,BUF,21,18,-3.0,38.0,72,5,55,Highmark Stadium,FALSE
2023-09-17,2023,2,FALSE,Kansas City Chiefs,Cincinnati Bengals,KAN,14,21,-3.5,38.0,72,5,55,Arrowhead Stadium,FALSE
2023-09-24,2023,3,FALSE,Dallas Cowboys,New York Giants,DAL,24,20,-4.5,41.0,72,5,55,AT&T Stadium,FALSE
2023-10-01,2023,4,FALSE,Green Bay Packers,Detroit Lions,GB,22,21,-3.0,41.0,72,5,55,Lambeau Field,FALSE
2023-10-08,2023,5,FALSE,Chicago Bears,Minnesota Vikings,MIN,17,21,-2.5,41.0,72,5,55,Soldier Field,FALSE
2023-10-15,2023,6,FALSE,Philadelphia Eagles,Washington Commanders,PHI,27,21,-7.5,44.0,72,5,55,Lincoln Financial Field,FALSE
2023-10-22,2023,7,FALSE,New England Patriots,New York Jets,NE,24,22,-3.0,44.0,72,5,55,Gillette Stadium,FALSE
2023-10-29,2023,8,FALSE,Pittsburgh Steelers,Cleveland Browns,PIT,28,17,-3.5,44.0,72,5,55,Acrisure Stadium,FALSE
2023-11-05,2023,9,FALSE,Houston Texans,Indianapolis Colts,HOU,20,21,-3.0,44.0,72,5,55,NRG Stadium,FALSE
2023-11-12,2023,10,FALSE,Atlanta Falcons,New Orleans Saints,ATL,24,25,-2.5,47.0,72,5,55,Mercedes-Benz Stadium,FALSE
2023-11-19,2023,11,FALSE,Los Angeles Rams,Seattle Seahawks,LAR,28,21,-3.5,47.0,72,5,55,SoFi Stadium,FALSE
2023-11-26,2023,12,FALSE,Tennessee Titans,Jacksonville Jaguars,JAX,20,21,-3.0,47.0,72,5,55,Nissan Stadium,FALSE
2023-12-03,2023,13,FALSE,Carolina Panthers,Tampa Bay Buccaneers,TB,21,26,-3.5,47.0,72,5,55,Bank of America Stadium,FALSE
2023-12-10,2023,14,FALSE,Denver Broncos,Los Angeles Chargers,DEN,27,24,-3.0,50.0,72,5,55,Empower Field at Mile High,FALSE
2023-12-17,2023,15,FALSE,Baltimore Ravens,Cincinnati Bengals,BAL,30,24,-7.0,50.0,72,5,55,M&T Bank Stadium,FALSE
2023-12-24,2023,16,FALSE,San Francisco 49ers,Arizona Cardinals,SF,21,28,-13.5,50.0,72,5,55,Levi's Stadium,FALSE
2023-12-31,2023,17,FALSE,New York Jets,New England Patriots,NYJ,17,20,-3.0,50.0,72,5,55,MetLife Stadium,FALSE
2023-09-11,2023,1,FALSE,Indianapolis Colts,Houston Texans,IND,31,28,-3.5,53.0,72,5,55,Lucas Oil Stadium,FALSE
2023-09-18,2023,2,FALSE,Las Vegas Raiders,Buffalo Bills,BUF,23,30,-7.0,53.0,72,5,55,Allegiant Stadium,FALSE
2023-09-25,2023,3,FALSE,Miami Dolphins,Denver Broncos,MIA,24,21,-6.5,53.0,72,5,55,Hard Rock Stadium,FALSE
```

Per-row outcome verification:

| row | home | away | total | line | over/under/push |
|---|---|---|---|---|---|
| 1 | 21 | 18 | 39 | 38 | over |
| 2 | 14 | 21 | 35 | 38 | under |
| 3 | 24 | 20 | 44 | 41 | over |
| 4 | 22 | 21 | 43 | 41 | over |
| 5 | 17 | 21 | 38 | 41 | under |
| 6 | 27 | 21 | 48 | 44 | over |
| 7 | 24 | 22 | 46 | 44 | over |
| 8 | 28 | 17 | 45 | 44 | over |
| 9 | 20 | 21 | 41 | 44 | under |
| 10 | 24 | 25 | 49 | 47 | over |
| 11 | 28 | 21 | 49 | 47 | over |
| 12 | 20 | 21 | 41 | 47 | under |
| 13 | 21 | 26 | 47 | 47 | **push** |
| 14 | 27 | 24 | 51 | 50 | over |
| 15 | 30 | 24 | 54 | 50 | over |
| 16 | 21 | 28 | 49 | 50 | under |
| 17 | 17 | 20 | 37 | 50 | under |
| 18 | 31 | 28 | 59 | 53 | over |
| 19 | 23 | 30 | 53 | 53 | **push** |
| 20 | 24 | 21 | 45 | 53 | under |

Wait — row 19 produces a push, not the under planned. Revise expected counts:

| Bucket | n | over | under | push |
|---|---|---|---|---|
| `total_le_39_5`  | 2 | 1 | 1 | 0 |
| `total_40_42_5`  | 3 | 2 | 1 | 0 |
| `total_43_45_5`  | 4 | 3 | 1 | 0 |
| `total_46_48_5`  | 4 | 2 | 1 | 1 |
| `total_49_51_5`  | 4 | 2 | 2 | 0 |
| `total_ge_52`    | 3 | 1 | 1 | 1 |

Total: 20 games = 11 overs + 7 unders + 2 pushes. Use these in T7.

- [ ] **Step 2: Verify file with `wc -l` and `Get-Content -TotalCount 5`**

```powershell
(Get-Content tests/fixtures/totals_20.csv | Measure-Object -Line).Lines
```

Expected: `21` (1 header + 20 data rows).

- [ ] **Step 3: Commit**

```powershell
git add tests/fixtures/totals_20.csv
git commit -m "test(totals): 20-game totals fixture spanning all 6 buckets"
```

---

## Task 7: `engine.totals.totals_by_line_bucket` aggregator

**Files:**
- Modify: `engine/totals.py` (add `TotalsReport` + `totals_by_line_bucket`)
- Modify: `tests/test_totals.py` (append aggregator tests using fixture)

- [ ] **Step 1: Append failing tests to `tests/test_totals.py`**

```python
from pathlib import Path

from engine.db import connect, init_schema
from engine.totals import TotalsReport, totals_by_line_bucket
from ingestion.loader import load_csv_to_db


def _build_db_from_fixture(tmp_path: Path, fixture: str) -> Path:
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    init_schema(conn)
    conn.close()
    load_csv_to_db(Path(fixture), db_path)
    return db_path


def test_totals_aggregator_returns_report_with_6_buckets(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/totals_20.csv")
    conn = connect(db)
    try:
        report = totals_by_line_bucket(conn)
    finally:
        conn.close()
    assert isinstance(report, TotalsReport)
    assert len(report.rows) == 6
    assert [r.bucket for r in report.rows] == BUCKET_ORDER_TOTALS


def test_totals_aggregator_per_bucket_counts_match_fixture(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/totals_20.csv")
    conn = connect(db)
    try:
        report = totals_by_line_bucket(conn)
    finally:
        conn.close()
    by = {r.bucket: r for r in report.rows}

    expected = {
        "total_le_39_5":  (2, 1, 1, 0),  # n, wins(over), losses(under), pushes
        "total_40_42_5":  (3, 2, 1, 0),
        "total_43_45_5":  (4, 3, 1, 0),
        "total_46_48_5":  (4, 2, 1, 1),
        "total_49_51_5":  (4, 2, 2, 0),
        "total_ge_52":    (3, 1, 1, 1),
    }
    for bucket, (n, w, l, p) in expected.items():
        m = by[bucket]
        assert (m.n, m.wins, m.losses, m.pushes) == (n, w, l, p), bucket


def test_totals_aggregator_total_counts_sum_to_20(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/totals_20.csv")
    conn = connect(db)
    try:
        report = totals_by_line_bucket(conn)
    finally:
        conn.close()
    total_n = sum(r.n for r in report.rows)
    assert total_n == 20
```

- [ ] **Step 2: Run, confirm fail**

```powershell
uv run pytest tests/test_totals.py -k aggregator -v
```

Expected: ImportError on `TotalsReport` / `totals_by_line_bucket`.

- [ ] **Step 3: Append `TotalsReport` and aggregator to `engine/totals.py`**

```python
import sqlite3
from dataclasses import dataclass

import pandas as pd

from engine.bucket_analysis import BucketMetrics, compute_metrics


@dataclass
class TotalsReport:
    rows: list[BucketMetrics]


def totals_by_line_bucket(conn: sqlite3.Connection) -> TotalsReport:
    """Aggregate over/under results into the 6 total-line buckets."""
    df = pd.read_sql_query(
        """
        SELECT g.season, b.total_line, b.total_result
        FROM games g
        JOIN betting_lines b ON b.game_id = g.game_id
        WHERE b.total_line IS NOT NULL
          AND b.total_result IS NOT NULL
        """,
        conn,
    )
    df["bucket"] = df["total_line"].apply(bucket_total)

    rows: list[BucketMetrics] = []
    for bucket in BUCKET_ORDER_TOTALS:
        sub = df[df["bucket"] == bucket]
        wins = int((sub["total_result"] == "over").sum())
        losses = int((sub["total_result"] == "under").sum())
        pushes = int((sub["total_result"] == "push").sum())

        by_season: dict[int, float] = {}
        if len(sub) > 0:
            for season, group in sub.groupby("season"):
                w = int((group["total_result"] == "over").sum())
                l_ = int((group["total_result"] == "under").sum())
                decided = w + l_
                if decided > 0:
                    by_season[int(season)] = w / decided

        rows.append(compute_metrics(bucket, wins, losses, pushes, by_season))

    return TotalsReport(rows=rows)
```

Add `from engine.totals import BUCKET_ORDER_TOTALS` to the top of `tests/test_totals.py` so the new tests resolve it.

- [ ] **Step 4: Run, confirm pass**

```powershell
uv run pytest tests/test_totals.py -v
```

Expected: 14 prior + 3 aggregator = 17 passed.

- [ ] **Step 5: Full suite + lint**

```powershell
uv run pytest -q
uv run ruff check .
```

- [ ] **Step 6: Commit**

```powershell
git add engine/totals.py tests/test_totals.py
git commit -m "feat(totals): totals_by_line_bucket aggregator + integration tests"
```

---

## Task 8: `tests/fixtures/moneyline_20.csv` — hand-built fixture

**Files:**
- Create: `tests/fixtures/moneyline_20.csv`

Goal: 20 games whose closing **spreads** derive into ML prices spanning all 11 ML buckets. Each game contributes **two** ML perspectives (home, away), so the aggregator sees 40 bet rows. We pick spreads so the derived ML buckets are unambiguous.

Reference: `derive_ml_from_spread` returns these for these spreads (from T3 verification):

| spread_home | ML_home bucket | ML_away bucket |
|---|---|---|
| -15.0 | ml_heavy_fav  | ml_heavy_dog  | (ML ≈ -890 / +583)
| -12.0 | ml_big_fav    | ml_big_dog    | (ML ≈ -496 / +373)
| -9.0  | ml_mid_fav    | ml_mid_dog    | (ML ≈ -319 / +254)
| -6.0  | ml_small_fav  | ml_small_dog  | (ML ≈ -220 / +180)
| -4.0  | ml_slight_fav | ml_slight_dog | (ML ≈ -178 / +144)
| -2.0  | ml_slight_fav | ml_slight_dog | (ML ≈ -135 / +115)
| 0.0   | ml_slight_fav | ml_slight_fav | (ML ≈ -110 / -110, both fall in slight_fav)

Note: the slight_fav/slight_dog split happens between -110 and +110. Spread 0 produces -110/-110 → both buckets are `ml_slight_fav`. To populate `ml_pickem` we need ML strictly above -110, which requires a slight away-favorite (positive home spread).

Use this spread/outcome menu to fill all 11 buckets:

| game | spread_home | score_home | score_away | home wins? | ML_home bucket | ML_away bucket |
|---|---|---|---|---|---|---|
| 1 | -15.0 | 35 | 7  | yes | ml_heavy_fav  | ml_heavy_dog  |
| 2 | -15.0 | 10 | 20 | no  | ml_heavy_fav  | ml_heavy_dog  |
| 3 | -12.0 | 30 | 10 | yes | ml_big_fav    | ml_big_dog    |
| 4 | -12.0 | 14 | 28 | no  | ml_big_fav    | ml_big_dog    |
| 5 | -9.0  | 24 | 14 | yes | ml_mid_fav    | ml_mid_dog    |
| 6 | -9.0  | 17 | 21 | no  | ml_mid_fav    | ml_mid_dog    |
| 7 | -6.0  | 27 | 17 | yes | ml_small_fav  | ml_small_dog  |
| 8 | -6.0  | 10 | 24 | no  | ml_small_fav  | ml_small_dog  |
| 9 | -4.0  | 21 | 14 | yes | ml_slight_fav | ml_slight_dog |
| 10 | -4.0 | 17 | 20 | no  | ml_slight_fav | ml_slight_dog |
| 11 | -2.0 | 24 | 20 | yes | ml_slight_fav | ml_slight_dog |
| 12 | -2.0 | 17 | 21 | no  | ml_slight_fav | ml_slight_dog |
| 13 | 0.0  | 21 | 17 | yes | ml_slight_fav | ml_slight_fav |
| 14 | 0.0  | 14 | 17 | no  | ml_slight_fav | ml_slight_fav |
| 15 | +2.0 | 17 | 24 | no  | ml_slight_dog | ml_slight_fav |
| 16 | +4.0 | 21 | 24 | no  | ml_slight_dog | ml_slight_fav |
| 17 | +6.0 | 17 | 27 | no  | ml_small_dog  | ml_small_fav  |
| 18 | +9.0 | 14 | 24 | no  | ml_mid_dog    | ml_mid_fav    |
| 19 | +12.0| 10 | 30 | no  | ml_big_dog    | ml_big_fav    |
| 20 | +15.0| 7  | 35 | no  | ml_heavy_dog  | ml_heavy_fav  |

The Kaggle CSV format encodes spreads via `team_favorite_id` + `spread_favorite` (magnitude). For each row:
- If `spread_home > 0` → home is dog → favorite is the away team. `spread_favorite = -spread_home`.
- If `spread_home < 0` → home is favorite. `team_favorite_id` = home team. `spread_favorite = spread_home` (negative magnitude in the source; loader handles it).
- If `spread_home == 0` → pickem; `team_favorite_id` = home (arbitrary), `spread_favorite = 0.0`.

The loader's `derive_spread_home_close()` interprets `spread_favorite` and the favorite's identity to produce `spread_home_close`.

- [ ] **Step 1: Create `tests/fixtures/moneyline_20.csv`**

```csv
schedule_date,schedule_season,schedule_week,schedule_playoff,team_home,team_away,team_favorite_id,score_home,score_away,spread_favorite,over_under_line,weather_temperature,weather_wind_mph,weather_humidity,stadium,stadium_neutral
2022-09-11,2022,1,FALSE,Buffalo Bills,Tampa Bay Buccaneers,BUF,35,7,-15.0,45.0,72,5,55,Highmark Stadium,FALSE
2022-09-18,2022,2,FALSE,Kansas City Chiefs,Carolina Panthers,KAN,10,20,-15.0,45.0,72,5,55,Arrowhead Stadium,FALSE
2022-09-25,2022,3,FALSE,Philadelphia Eagles,Houston Texans,PHI,30,10,-12.0,45.0,72,5,55,Lincoln Financial Field,FALSE
2022-10-02,2022,4,FALSE,San Francisco 49ers,Indianapolis Colts,SF,14,28,-12.0,45.0,72,5,55,Levi's Stadium,FALSE
2022-10-09,2022,5,FALSE,Baltimore Ravens,New York Giants,BAL,24,14,-9.0,45.0,72,5,55,M&T Bank Stadium,FALSE
2022-10-16,2022,6,FALSE,Dallas Cowboys,Chicago Bears,DAL,17,21,-9.0,45.0,72,5,55,AT&T Stadium,FALSE
2022-10-23,2022,7,FALSE,Cincinnati Bengals,Atlanta Falcons,CIN,27,17,-6.0,45.0,72,5,55,Paycor Stadium,FALSE
2022-10-30,2022,8,FALSE,Miami Dolphins,Washington Commanders,MIA,10,24,-6.0,45.0,72,5,55,Hard Rock Stadium,FALSE
2022-11-06,2022,9,FALSE,Detroit Lions,Las Vegas Raiders,DET,21,14,-4.0,45.0,72,5,55,Ford Field,FALSE
2022-11-13,2022,10,FALSE,Pittsburgh Steelers,New England Patriots,PIT,17,20,-4.0,45.0,72,5,55,Acrisure Stadium,FALSE
2022-11-20,2022,11,FALSE,Seattle Seahawks,Tennessee Titans,SEA,24,20,-2.0,45.0,72,5,55,Lumen Field,FALSE
2022-11-27,2022,12,FALSE,Denver Broncos,Cleveland Browns,DEN,17,21,-2.0,45.0,72,5,55,Empower Field at Mile High,FALSE
2022-12-04,2022,13,FALSE,New York Jets,Jacksonville Jaguars,NYJ,21,17,0.0,45.0,72,5,55,MetLife Stadium,FALSE
2022-12-11,2022,14,FALSE,Arizona Cardinals,Minnesota Vikings,ARI,14,17,0.0,45.0,72,5,55,State Farm Stadium,FALSE
2022-12-18,2022,15,FALSE,New Orleans Saints,Green Bay Packers,GB,17,24,-2.0,45.0,72,5,55,Caesars Superdome,FALSE
2022-12-25,2022,16,FALSE,Los Angeles Chargers,Los Angeles Rams,LAR,21,24,-4.0,45.0,72,5,55,SoFi Stadium,FALSE
2023-01-01,2022,17,FALSE,New York Giants,Buffalo Bills,BUF,17,27,-6.0,45.0,72,5,55,MetLife Stadium,FALSE
2023-01-08,2022,18,FALSE,Houston Texans,Kansas City Chiefs,KAN,14,24,-9.0,45.0,72,5,55,NRG Stadium,FALSE
2022-09-12,2022,1,FALSE,Carolina Panthers,Philadelphia Eagles,PHI,10,30,-12.0,45.0,72,5,55,Bank of America Stadium,FALSE
2022-09-19,2022,2,FALSE,Indianapolis Colts,San Francisco 49ers,SF,7,35,-15.0,45.0,72,5,55,Lucas Oil Stadium,FALSE
```

- [ ] **Step 2: Verify the file**

```powershell
(Get-Content tests/fixtures/moneyline_20.csv | Measure-Object -Line).Lines
```

Expected: `21`.

- [ ] **Step 3: Commit**

```powershell
git add tests/fixtures/moneyline_20.csv
git commit -m "test(moneyline): 20-game fixture spanning all 11 derived ML buckets"
```

---

## Task 9: `engine.moneyline.moneyline_by_odds_bucket` aggregator

**Files:**
- Modify: `engine/moneyline.py` (add `MoneylineReport` + aggregator + payout helper)
- Modify: `tests/test_moneyline.py` (append aggregator tests using fixture)

The aggregator emits one bet row per side per game: 20 games × 2 sides = 40 bet rows in total.

**Expected per-bucket aggregated counts (hand-derived from T8 fixture):**

| Bucket | n | wins | losses | pushes |
|---|---|---|---|---|
| `ml_heavy_fav`  | 4  | 2 | 2 | 0 |
| `ml_big_fav`    | 4  | 2 | 2 | 0 |
| `ml_mid_fav`    | 4  | 2 | 2 | 0 |
| `ml_small_fav`  | 4  | 2 | 2 | 0 |
| `ml_slight_fav` | 8  | 5 | 3 | 0 |
| `ml_pickem`     | 0  | 0 | 0 | 0 |
| `ml_slight_dog` | 8  | 1 | 7 | 0 |
| `ml_small_dog`  | 2  | 0 | 2 | 0 |
| `ml_mid_dog`    | 2  | 0 | 2 | 0 |
| `ml_big_dog`    | 2  | 0 | 2 | 0 |
| `ml_heavy_dog`  | 2  | 0 | 2 | 0 |

Per-game breakdown (each row in T8 fixture → 2 rows here, home perspective then away):

- Game 1 (spread -15, home wins 35-7): home/heavy_fav/WIN, away/heavy_dog/LOSS
- Game 2 (spread -15, home loses 10-20): home/heavy_fav/LOSS, away/heavy_dog/WIN
- Game 3 (spread -12, home wins 30-10): home/big_fav/WIN, away/big_dog/LOSS
- Game 4 (spread -12, home loses 14-28): home/big_fav/LOSS, away/big_dog/WIN
- Game 5 (spread -9, home wins): home/mid_fav/WIN, away/mid_dog/LOSS
- Game 6 (spread -9, home loses): home/mid_fav/LOSS, away/mid_dog/WIN
- Game 7 (spread -6, home wins): home/small_fav/WIN, away/small_dog/LOSS
- Game 8 (spread -6, home loses): home/small_fav/LOSS, away/small_dog/WIN
- Game 9 (spread -4, home wins): home/slight_fav/WIN, away/slight_dog/LOSS
- Game 10 (spread -4, home loses): home/slight_fav/LOSS, away/slight_dog/WIN
- Game 11 (spread -2, home wins): home/slight_fav/WIN, away/slight_dog/LOSS
- Game 12 (spread -2, home loses): home/slight_fav/LOSS, away/slight_dog/WIN
- Game 13 (spread 0, home wins): home/slight_fav/WIN, away/slight_fav/LOSS
- Game 14 (spread 0, home loses): home/slight_fav/LOSS, away/slight_fav/WIN
- Game 15 (spread +2, home loses 17-24): home/slight_dog/LOSS, away/slight_fav/WIN
- Game 16 (spread +4, home loses 21-24): home/slight_dog/LOSS, away/slight_fav/WIN
- Game 17 (spread +6, home loses 17-27): home/small_dog/LOSS, away/small_fav/WIN
- Game 18 (spread +9, home loses 14-24): home/mid_dog/LOSS, away/mid_fav/WIN
- Game 19 (spread +12, home loses 10-30): home/big_dog/LOSS, away/big_fav/WIN
- Game 20 (spread +15, home loses 7-35): home/heavy_dog/LOSS, away/heavy_fav/WIN

Tally:
- `ml_heavy_fav`: g1H(W), g2H(L), g20A(W), g_other_H... wait, recount carefully.

Strict per-bucket recount:
- `ml_heavy_fav`: g1 home (W), g2 home (L), g20 away (W), no others → 3 entries??

Wait — the heavy fav bucket comes from spreads of magnitude ≥ ~14 (since -15 → -890 ML). Heavy fav also receives any home/away with ML ≤ -300. Let me derive what each side's ML is for each spread and walk the bucket assignment:

| spread_home | ML_home | ML_away | home bucket | away bucket |
|---|---|---|---|---|
| -15.0 | ≈-890 | ≈+583 | ml_heavy_fav | ml_heavy_dog |
| -12.0 | ≈-496 | ≈+373 | ml_heavy_fav | ml_heavy_dog |
| -9.0  | ≈-319 | ≈+254 | ml_heavy_fav | ml_mid_dog |
| -6.0  | ≈-220 | ≈+180 | ml_mid_fav   | ml_mid_dog |
| -4.0  | ≈-178 | ≈+144 | ml_mid_fav   | ml_small_dog |
| -2.0  | ≈-135 | ≈+115 | ml_small_fav | ml_slight_dog |
|  0.0  | ≈-110 | ≈-110 | ml_slight_fav| ml_slight_fav |
| +2.0  | ≈+115 | ≈-135 | ml_slight_dog| ml_small_fav |
| +4.0  | ≈+144 | ≈-178 | ml_small_dog | ml_mid_fav |
| +6.0  | ≈+180 | ≈-220 | ml_mid_dog   | ml_mid_fav |
| +9.0  | ≈+254 | ≈-319 | ml_mid_dog   | ml_heavy_fav |
| +12.0 | ≈+373 | ≈-496 | ml_heavy_dog | ml_heavy_fav |
| +15.0 | ≈+583 | ≈-890 | ml_heavy_dog | ml_heavy_fav |

This changes the prior bucket plan — many buckets I planned for separately are actually heavy_fav. Re-tally per fixture:

| game | spread | home result | home bucket | away bucket |
|---|---|---|---|---|
| 1  | -15 | W  | ml_heavy_fav | ml_heavy_dog  |
| 2  | -15 | L  | ml_heavy_fav | ml_heavy_dog  |
| 3  | -12 | W  | ml_heavy_fav | ml_heavy_dog  |
| 4  | -12 | L  | ml_heavy_fav | ml_heavy_dog  |
| 5  | -9  | W  | ml_heavy_fav | ml_mid_dog    |
| 6  | -9  | L  | ml_heavy_fav | ml_mid_dog    |
| 7  | -6  | W  | ml_mid_fav   | ml_mid_dog    |
| 8  | -6  | L  | ml_mid_fav   | ml_mid_dog    |
| 9  | -4  | W  | ml_mid_fav   | ml_small_dog  |
| 10 | -4  | L  | ml_mid_fav   | ml_small_dog  |
| 11 | -2  | W  | ml_small_fav | ml_slight_dog |
| 12 | -2  | L  | ml_small_fav | ml_slight_dog |
| 13 | 0   | W  | ml_slight_fav| ml_slight_fav |
| 14 | 0   | L  | ml_slight_fav| ml_slight_fav |
| 15 | +2  | L  | ml_slight_dog| ml_small_fav  |
| 16 | +4  | L  | ml_small_dog | ml_mid_fav    |
| 17 | +6  | L  | ml_mid_dog   | ml_mid_fav    |
| 18 | +9  | L  | ml_mid_dog   | ml_heavy_fav  |
| 19 | +12 | L  | ml_heavy_dog | ml_heavy_fav  |
| 20 | +15 | L  | ml_heavy_dog | ml_heavy_fav  |

Aggregated (W=side wins, L=side loses):

| Bucket | n | W | L |
|---|---|---|---|
| ml_heavy_fav | 8 | g1H(W), g3H(W), g5H(W), g18A(W), g19A(W), g20A(W) = 6W; g2H(L), g4H(L), g6H(L) = 3L → wait, that's 9 entries |

Let me carefully count again, one entry per side per game:
- ml_heavy_fav entries: 1H, 2H, 3H, 4H, 5H, 6H (from spreads -15/-12/-9 home perspective) + 18A, 19A, 20A (from spreads +9/+12/+15 away perspective) = **9 entries**
  - W: 1H (W), 3H (W), 5H (W), 18A (away wins game 18: 24>14 yes W), 19A (away 30>10 W), 20A (away 35>7 W) = 6W
  - L: 2H (L), 4H (L), 6H (L) = 3L
  - n=9, W=6, L=3, P=0

- ml_heavy_dog entries: 1A, 2A, 3A, 4A (from -15/-12 away perspective) + 19H, 20H (from +12/+15 home perspective) = **6 entries**
  - W: 2A (game 2 away wins 20>10 W), 4A (28>14 W) = 2W
  - L: 1A (away loses 7<35 L), 3A (10<30 L), 19H (10<30 L), 20H (7<35 L) = 4L
  - n=6, W=2, L=4

- ml_mid_fav entries: 7H, 8H, 9H, 10H (from -6/-4 home) + 16A, 17A (from +4/+6 away) = **6 entries**
  - W: 7H (27>17 W), 9H (21>14 W), 16A (24>21 W), 17A (27>17 W) = 4W
  - L: 8H (10<24 L), 10H (17<20 L) = 2L
  - n=6, W=4, L=2

- ml_mid_dog entries: 5A, 6A, 7A, 8A (from -9/-6 away) + 17H, 18H (from +6/+9 home) = **6 entries**
  - W: 6A (away 21>17 W), 8A (away 24>10 W) = 2W
  - L: 5A (14<24 L), 7A (17<27 L), 17H (17<27 L), 18H (14<24 L) = 4L
  - n=6, W=2, L=4

- ml_small_fav entries: 11H, 12H (from -2 home) + 15A (from +2 away) = **3 entries**
  - W: 11H (24>20 W), 15A (24>17 W) = 2W
  - L: 12H (17<21 L) = 1L
  - n=3, W=2, L=1

- ml_small_dog entries: 9A, 10A (from -4 away) + 16H (from +4 home) = **3 entries**
  - W: 10A (20>17 W) = 1W
  - L: 9A (14<21 L), 16H (21<24 L) = 2L
  - n=3, W=1, L=2

- ml_slight_fav entries: 13H, 13A, 14H, 14A (from spread 0 both sides) = **4 entries**
  - W: 13H (21>17 W), 14A (17>14 W) = 2W
  - L: 13A (17<21 L), 14H (14<17 L) = 2L
  - n=4, W=2, L=2

- ml_slight_dog entries: 11A, 12A (from -2 away) + 15H (from +2 home) = **3 entries**
  - W: 12A (21>17 W) = 1W
  - L: 11A (20<24 L), 15H (17<24 L) = 2L
  - n=3, W=1, L=2

- ml_pickem entries: 0 (spread 0 produces -110/-110 which lands in slight_fav per the boundary)
  - n=0

Verification: total entries = 9+6+6+6+3+3+4+3+0 = 40 ✓ (20 games × 2 sides).

Updated expected aggregator table:

| Bucket | n | wins | losses | pushes |
|---|---|---|---|---|
| `ml_heavy_fav`  | 9 | 6 | 3 | 0 |
| `ml_big_fav`    | 0 | 0 | 0 | 0 |
| `ml_mid_fav`    | 6 | 4 | 2 | 0 |
| `ml_small_fav`  | 3 | 2 | 1 | 0 |
| `ml_slight_fav` | 4 | 2 | 2 | 0 |
| `ml_pickem`     | 0 | 0 | 0 | 0 |
| `ml_slight_dog` | 3 | 1 | 2 | 0 |
| `ml_small_dog`  | 3 | 1 | 2 | 0 |
| `ml_mid_dog`    | 6 | 2 | 4 | 0 |
| `ml_big_dog`    | 0 | 0 | 0 | 0 |
| `ml_heavy_dog`  | 6 | 2 | 4 | 0 |

Total wins = 6+4+2+2+1+1+2+2 = 20. Total losses = 3+2+1+2+2+2+4+4 = 20. Sanity: 20 games × 2 sides, each side is W or L (no ties in fixture) = 40 ✓.

- [ ] **Step 1: Append failing aggregator tests to `tests/test_moneyline.py`**

```python
from pathlib import Path

from engine.db import connect, init_schema
from engine.moneyline import MoneylineReport, moneyline_by_odds_bucket
from ingestion.loader import load_csv_to_db


def _build_db_from_fixture(tmp_path: Path, fixture: str) -> Path:
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    init_schema(conn)
    conn.close()
    load_csv_to_db(Path(fixture), db_path)
    return db_path


def test_moneyline_aggregator_returns_report_with_11_buckets(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/moneyline_20.csv")
    conn = connect(db)
    try:
        report = moneyline_by_odds_bucket(conn)
    finally:
        conn.close()
    assert isinstance(report, MoneylineReport)
    assert len(report.rows) == 11
    assert [r.bucket for r in report.rows] == BUCKET_ORDER_ML


def test_moneyline_aggregator_per_bucket_counts_match_fixture(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/moneyline_20.csv")
    conn = connect(db)
    try:
        report = moneyline_by_odds_bucket(conn)
    finally:
        conn.close()
    by = {r.bucket: r for r in report.rows}

    expected = {
        "ml_heavy_fav":  (9, 6, 3, 0),
        "ml_big_fav":    (0, 0, 0, 0),
        "ml_mid_fav":    (6, 4, 2, 0),
        "ml_small_fav":  (3, 2, 1, 0),
        "ml_slight_fav": (4, 2, 2, 0),
        "ml_pickem":     (0, 0, 0, 0),
        "ml_slight_dog": (3, 1, 2, 0),
        "ml_small_dog":  (3, 1, 2, 0),
        "ml_mid_dog":    (6, 2, 4, 0),
        "ml_big_dog":    (0, 0, 0, 0),
        "ml_heavy_dog":  (6, 2, 4, 0),
    }
    for bucket, (n, w, l_, p) in expected.items():
        m = by[bucket]
        assert (m.n, m.wins, m.losses, m.pushes) == (n, w, l_, p), bucket


def test_moneyline_aggregator_total_entries_is_40(tmp_path: Path):
    db = _build_db_from_fixture(tmp_path, "tests/fixtures/moneyline_20.csv")
    conn = connect(db)
    try:
        report = moneyline_by_odds_bucket(conn)
    finally:
        conn.close()
    total_n = sum(r.n for r in report.rows)
    assert total_n == 40  # 20 games * 2 sides


def test_moneyline_payout_helper_loss_returns_minus_one():
    from engine.moneyline import _payout_for_bet
    assert _payout_for_bet(ml_price=-150, won=False) == -1.0


def test_moneyline_payout_helper_win_at_minus_110_pays_100_over_110():
    from engine.moneyline import _payout_for_bet
    assert _payout_for_bet(ml_price=-110, won=True) == pytest.approx(100.0 / 110.0)


def test_moneyline_payout_helper_win_at_plus_150_pays_1_50():
    from engine.moneyline import _payout_for_bet
    assert _payout_for_bet(ml_price=+150, won=True) == pytest.approx(1.50)


def test_moneyline_payout_helper_push_returns_zero():
    from engine.moneyline import _payout_for_bet
    assert _payout_for_bet(ml_price=-110, won=None) == 0.0
```

Also add `from engine.moneyline import BUCKET_ORDER_ML` to the file's imports.

- [ ] **Step 2: Run, confirm fail**

```powershell
uv run pytest tests/test_moneyline.py -k "aggregator or payout" -v
```

Expected: `ImportError`.

- [ ] **Step 3: Append the aggregator and payout helper to `engine/moneyline.py`**

```python
import sqlite3
from dataclasses import dataclass

import pandas as pd

from engine.bucket_analysis import BucketMetrics, compute_metrics


def _payout_for_bet(ml_price: int, won: bool | None) -> float:
    """Net PnL of a 1-unit moneyline bet.

    won=True  → +odds/100 if positive American, +100/|odds| if negative
    won=False → -1.0
    won=None  → 0.0 (push, e.g. NFL tie)
    """
    if won is None:
        return 0.0
    if not won:
        return -1.0
    if ml_price > 0:
        return ml_price / 100.0
    return 100.0 / abs(ml_price)


def _outcome(home_score: int, away_score: int, side: str) -> bool | None:
    """Return True if `side` won outright, False if lost, None for tie."""
    if home_score == away_score:
        return None
    home_won = home_score > away_score
    return home_won if side == "home" else (not home_won)


@dataclass
class MoneylineReport:
    rows: list[BucketMetrics]


def moneyline_by_odds_bucket(conn: sqlite3.Connection) -> MoneylineReport:
    """Aggregate moneyline outcomes into 11 derived-ML buckets.

    Each game contributes two bet rows (home perspective + away perspective).
    Prices are derived from spread via derive_ml_from_spread().
    ROI is dollar-weighted using per-bet payouts because prices vary across rows.
    """
    df = pd.read_sql_query(
        """
        SELECT g.season, b.spread_home_close, g.score_home, g.score_away
        FROM games g
        JOIN betting_lines b ON b.game_id = g.game_id
        WHERE b.spread_home_close IS NOT NULL
          AND g.score_home IS NOT NULL
          AND g.score_away IS NOT NULL
        """,
        conn,
    )

    # Build per-side bet records
    records: list[dict] = []
    for _idx, row in df.iterrows():
        derived = derive_ml_from_spread(float(row["spread_home_close"]))
        if derived is None:
            continue
        ml_home, ml_away = derived
        for side, ml in (("home", ml_home), ("away", ml_away)):
            won = _outcome(int(row["score_home"]), int(row["score_away"]), side)
            records.append({
                "season": int(row["season"]),
                "side": side,
                "ml": ml,
                "bucket": bucket_ml(ml),
                "won": won,
                "payout": _payout_for_bet(ml, won),
            })
    bet_df = pd.DataFrame.from_records(records)

    rows: list[BucketMetrics] = []
    for bucket in BUCKET_ORDER_ML:
        sub = bet_df[bet_df["bucket"] == bucket] if not bet_df.empty else bet_df
        wins = int((sub["won"] == True).sum()) if not sub.empty else 0  # noqa: E712
        losses = int((sub["won"] == False).sum()) if not sub.empty else 0  # noqa: E712
        pushes = int(sub["won"].isna().sum()) if not sub.empty else 0
        payouts = sub["payout"].tolist() if not sub.empty else []

        by_season: dict[int, float] = {}
        if not sub.empty:
            for season, group in sub.groupby("season"):
                w = int((group["won"] == True).sum())  # noqa: E712
                l_ = int((group["won"] == False).sum())  # noqa: E712
                decided = w + l_
                if decided > 0:
                    by_season[int(season)] = w / decided

        rows.append(compute_metrics(bucket, wins, losses, pushes, by_season, payouts=payouts))

    return MoneylineReport(rows=rows)
```

- [ ] **Step 4: Run, confirm pass**

```powershell
uv run pytest tests/test_moneyline.py -v
```

Expected: prior tests + 4 payout helper + 3 aggregator = ~40 passed.

- [ ] **Step 5: Full suite + lint**

```powershell
uv run pytest -q
uv run ruff check .
```

- [ ] **Step 6: Commit**

```powershell
git add engine/moneyline.py tests/test_moneyline.py
git commit -m "feat(moneyline): moneyline_by_odds_bucket aggregator with variable-payout ROI"
```

---

## Task 10: `engine.totals` CLI entry

**Files:**
- Modify: `engine/totals.py` (add `_main` and `__main__` guard)

- [ ] **Step 1: Append the CLI entry to `engine/totals.py`**

```python
import sys
from pathlib import Path

from engine.bucket_analysis import DISCLAIMER, format_table, write_csv
from engine.db import connect


def _main(_argv: list[str] | None = None) -> int:
    db_path = Path("data/db/nfl_betting.sqlite")
    out_csv = Path("data/processed/totals_by_bucket.csv")
    if not db_path.exists():
        print(
            f"Database not found at {db_path}. "
            "Run `python -m ingestion.loader data/raw/spreadspoke_scores.csv` first.",
            file=sys.stderr,
        )
        return 2

    conn = connect(db_path)
    try:
        report = totals_by_line_bucket(conn)
    finally:
        conn.close()

    print(format_table(report.rows))
    print()
    print(DISCLAIMER)

    write_csv(report.rows, out_csv)
    print(f"\nCSV written to {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
```

- [ ] **Step 2: Smoke test the CLI against the existing DB (no test file — manual check)**

```powershell
uv run python -m engine.totals
```

Expected:
- A 6-row tabulated table prints to stdout
- Trailing disclaimer line
- `data/processed/totals_by_bucket.csv` written

If the DB doesn't exist locally (CI / fresh checkout), the command exits 2 — this is correct and tested in T13.

- [ ] **Step 3: Full suite + lint**

```powershell
uv run pytest -q
uv run ruff check .
```

- [ ] **Step 4: Commit**

```powershell
git add engine/totals.py
git commit -m "feat(totals): CLI entry, tabulated stdout, CSV output, disclaimer"
```

---

## Task 11: `engine.moneyline` CLI entry

**Files:**
- Modify: `engine/moneyline.py` (add `_main` and `__main__` guard + derivation note)

- [ ] **Step 1: Append the CLI entry to `engine/moneyline.py`**

```python
import sys
from pathlib import Path

from engine.bucket_analysis import DISCLAIMER, format_table, write_csv
from engine.db import connect


DERIVATION_NOTE = (
    "NOTE: Moneyline prices derived from closing spreads via normal-CDF + vig "
    "(SIGMA=13.86, OVERROUND=1.04762). These are NOT real historical sportsbook ML prices."
)


def _main(_argv: list[str] | None = None) -> int:
    db_path = Path("data/db/nfl_betting.sqlite")
    out_csv = Path("data/processed/moneyline_by_bucket.csv")
    if not db_path.exists():
        print(
            f"Database not found at {db_path}. "
            "Run `python -m ingestion.loader data/raw/spreadspoke_scores.csv` first.",
            file=sys.stderr,
        )
        return 2

    conn = connect(db_path)
    try:
        report = moneyline_by_odds_bucket(conn)
    finally:
        conn.close()

    print(DERIVATION_NOTE)
    print()
    print(format_table(report.rows))
    print()
    print(DISCLAIMER)

    # Custom CSV: prefix the derivation note as a comment line before the standard disclaimer
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_csv(report.rows, out_csv)
    # Prepend the derivation note as an additional comment line above the disclaimer
    text = out_csv.read_text(encoding="utf-8")
    out_csv.write_text(f"# {DERIVATION_NOTE}\n{text}", encoding="utf-8")
    print(f"\nCSV written to {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
```

- [ ] **Step 2: Smoke-run the CLI**

```powershell
uv run python -m engine.moneyline
```

Expected:
- Derivation note prints first
- 11-row table follows
- Disclaimer at end
- `data/processed/moneyline_by_bucket.csv` written, lines 1–2 are `# NOTE:` comment then `# Past performance...` comment, then header row

- [ ] **Step 3: Full suite + lint**

```powershell
uv run pytest -q
uv run ruff check .
```

- [ ] **Step 4: Commit**

```powershell
git add engine/moneyline.py
git commit -m "feat(moneyline): CLI entry, derivation note, tabulated stdout, CSV output"
```

---

## Task 12: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append the new section after "Generate the ATS report"**

```markdown
## Generate the totals report

```powershell
uv run python -m engine.totals
```

Prints a per-bucket over/under table to stdout and writes `data/processed/totals_by_bucket.csv`.

## Generate the moneyline report

```powershell
uv run python -m engine.moneyline
```

Prints a per-bucket moneyline table to stdout and writes `data/processed/moneyline_by_bucket.csv`.

**Important caveat:** The Kaggle dataset does not contain historical moneyline prices. This report **derives** ML prices from closing spreads using a standard NFL margin-of-victory model (normal CDF with σ ≈ 13.86) plus a -110/-110-equivalent vig. The derivation note is printed at the top of the output and included as a comment in the CSV. Findings reflect the spread market's efficiency expressed in moneyline form, not the moneyline market's independent efficiency.
```

- [ ] **Step 2: Update the "Slice scope" section to reflect Slice 2 shipping**

Find the existing scope blurb and update it to read:

```markdown
## Scope

- **Slice 1 (complete):** ingestion, schema, statistics utilities, ATS-by-spread-bucket analysis.
- **Slice 2 (complete):** totals-by-line-bucket and moneyline-by-odds-bucket analysis (ML prices derived from spreads).
- **Deferred to later slices:** live odds ingestion, best-bets engine, predictive modeling, interactive dashboard.
```

- [ ] **Step 3: Commit**

```powershell
git add README.md
git commit -m "docs(readme): document totals + moneyline commands and ML derivation caveat"
```

---

## Task 13: Real-data smoke test

**Files:** none (verification step)

Assumes `data/db/nfl_betting.sqlite` already exists with 5,680 games loaded from Slice 1.

- [ ] **Step 1: Verify DB exists**

```powershell
Test-Path data/db/nfl_betting.sqlite
```

Expected: `True`. If `False`, re-run the Slice 1 loader first: `uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv`.

- [ ] **Step 2: Run the totals CLI against the real DB**

```powershell
uv run python -m engine.totals
```

Expected:
- 6 rows printed
- Each populated bucket shows n in the hundreds (NFL totals cluster heavily in 43–48.5 range)
- Tail buckets (`total_le_39_5`, `total_ge_52`) may show smaller n and `*` low-sample marker
- `data/processed/totals_by_bucket.csv` written

- [ ] **Step 3: Run the moneyline CLI**

```powershell
uv run python -m engine.moneyline
```

Expected:
- Derivation note prints first
- 11 rows printed; total n across all buckets ≈ 11,360 (5,680 games × 2 sides)
- Heavy fav/dog buckets balance (every heavy fav has a heavy dog on the other side)
- Pickem bucket likely empty or near-empty (boundary effect from spread 0 → -110/-110)
- `data/processed/moneyline_by_bucket.csv` written, includes both comment lines

- [ ] **Step 4: Sanity-check the CSV outputs**

```powershell
Get-Content data/processed/totals_by_bucket.csv -TotalCount 3
Get-Content data/processed/moneyline_by_bucket.csv -TotalCount 4
```

Expected:
- Totals CSV: line 1 `# Past performance...`, line 2 header row, line 3 first data row
- ML CSV: line 1 `# NOTE: Moneyline prices...`, line 2 `# Past performance...`, line 3 header, line 4 first data row

- [ ] **Step 5: Full test suite one more time**

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: every test green, ruff clean.

- [ ] **Step 6: No commit needed for this task** — verification only.

---

## Task 14: Tag Slice 2 milestone

**Files:** none

- [ ] **Step 1: Confirm a clean working tree**

```powershell
git status
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 2: Tag the slice**

```powershell
git tag -a slice2-complete -m "Slice 2: totals + moneyline historical analysis"
```

- [ ] **Step 3: Verify**

```powershell
git tag
```

Expected: `slice1-complete` and `slice2-complete` both listed.

---

## Slice 2 — Definition of Done checklist

- [ ] `engine/bucket_analysis.py` exists; `engine/ats.py` imports from it; all prior Slice 1 tests still pass.
- [ ] `engine/stats_utils.dollar_weighted_roi` exists with 4 tests.
- [ ] `engine/totals.py` has `bucket_total`, `totals_by_line_bucket`, and CLI entry.
- [ ] `engine/moneyline.py` has `derive_ml_from_spread`, `bucket_ml`, `moneyline_by_odds_bucket`, and CLI entry.
- [ ] `tests/fixtures/totals_20.csv` and `tests/fixtures/moneyline_20.csv` exist with hand-verified outcomes.
- [ ] `uv run pytest -q` reports ~165+ tests passing (119 Slice 1 + ~45 Slice 2 new).
- [ ] `uv run ruff check .` clean.
- [ ] `uv run python -m engine.totals` populates `data/processed/totals_by_bucket.csv`.
- [ ] `uv run python -m engine.moneyline` populates `data/processed/moneyline_by_bucket.csv` with derivation note.
- [ ] README updated to document the two new commands and the ML derivation caveat.
- [ ] Tag `slice2-complete` cut.
