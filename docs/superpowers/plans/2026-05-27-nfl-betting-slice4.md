# NFL Betting Analytics — Slice 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real-line statistical rigor across all three markets (ATS, totals, moneyline) and produce a unified ranked report — `credible_edges.csv` — listing the buckets that meet four credibility thresholds.

**Architecture:** Additive over existing engine modules. One new metric (`profitable_seasons_pct`) added to the shared `BucketMetrics`. `compare_ml_prices` extended with bootstrap CI / p-value / per-season real_roi so ML buckets carry the same enrichment. One new `engine/credible_edges.py` module reads the three per-market CSVs, normalizes to a common shape, filters by four thresholds, ranks by Wilson lower bound, and writes the unified report. One one-off `scripts/cross_check_ats_totals.py` validates Kaggle spreads/totals against nflverse on the 2020–2024 overlap.

**Tech Stack:** Python 3.11+, `uv`, `pandas`, `numpy`, `scipy`, `tabulate`, `nfl_data_py`, `pytest`, `ruff`, SQLite. Same as Slice 3, no new deps.

**Spec:** `docs/superpowers/specs/2026-05-27-nfl-betting-slice4-design.md`

---

## Conventions used throughout this plan

- **All commands run from the project root** `C:\Users\ktber\projects\sports-betting`.
- **All commands assume PowerShell.** Forward slashes in `uv`/`pytest` arguments are fine.
- **Every task that changes code ends with a commit.** Conventional Commits (`feat:`, `refactor:`, `test:`, `chore:`, `docs:`).
- **Run `uv run pytest -q` after each task** to confirm the prior 222 tests are still green.
- **Floating-point assertions use `pytest.approx`** (DNR: `.wolf/cerebrum.md` 2026-05-27).
- **Avoid single-char `l` in loop unpacking** (DNR: ruff E741).
- **Scope imports tightly per task** (DNR: ruff F401).
- **Bootstrap functions use seed=42** for deterministic test results.

---

## File-level decomposition

| File | Responsibility | Lifecycle in Slice 4 |
|---|---|---|
| `engine/bucket_analysis.py` | Add `profitable_seasons_pct` to `BucketMetrics`; compute in `compute_metrics`; emit in `format_table` + `write_csv` | **MODIFY** (T1) |
| `tests/test_bucket_analysis.py` | Tests for new metric | **MODIFY** (T1) |
| `engine/stats_utils.py` | Add `bootstrap_mean_ci` and `bootstrap_pvalue_mean_gt_zero` helpers | **MODIFY** (T2) |
| `tests/test_stats_utils.py` | Tests for bootstrap helpers | **MODIFY** (T2) |
| `engine/validation.py` | Extend `BucketComparison` + `_build_bucket_comparisons` with ci_low/ci_high/p_value/profitable_seasons_pct; update CSV writer | **MODIFY** (T3) |
| `tests/test_validation.py` | Tests for per-season real_roi + bootstrap stats on ML | **MODIFY** (T3) |
| `scripts/cross_check_ats_totals.py` | One-time Kaggle-vs-nflverse spread/total cross-check | **NEW** (T4) |
| `docs/superpowers/notes/2026-05-28-kaggle-nflverse-crosscheck.md` | Cross-check findings | **NEW** (T4) |
| `engine/credible_edges.py` | Cross-market ranker + CLI | **NEW** (T5, T6) |
| `tests/test_credible_edges.py` | Tests with synthetic per-market CSVs | **NEW** (T5, T6) |
| `README.md` | Slice 4 section + headline finding | **MODIFY** (T8) |

---

## Task 1: Add `profitable_seasons_pct` to `BucketMetrics`

**Files:**
- Modify: `engine/bucket_analysis.py`
- Modify: `tests/test_bucket_analysis.py`

Purpose: extend the shared bucket-metrics dataclass with a new "share of seasons where this bucket was profitable" metric. ATS and totals pick it up automatically (they call `compute_metrics`); ML buckets are handled separately in T3.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_bucket_analysis.py`:

```python
import math

import pytest


def test_profitable_seasons_pct_all_profitable():
    from engine.bucket_analysis import compute_metrics
    by_season = {2020: 0.55, 2021: 0.60, 2022: 0.53, 2023: 0.58}
    m = compute_metrics("test", wins=50, losses=40, pushes=0, by_season=by_season)
    assert m.profitable_seasons_pct == pytest.approx(1.0)


def test_profitable_seasons_pct_none_profitable():
    from engine.bucket_analysis import compute_metrics
    by_season = {2020: 0.50, 2021: 0.48, 2022: 0.51, 2023: 0.45}
    m = compute_metrics("test", wins=50, losses=60, pushes=0, by_season=by_season)
    assert m.profitable_seasons_pct == pytest.approx(0.0)


def test_profitable_seasons_pct_mixed():
    from engine.bucket_analysis import compute_metrics
    by_season = {2020: 0.55, 2021: 0.45, 2022: 0.60, 2023: 0.50}
    # 2/4 seasons strictly above breakeven 0.5238 → 0.5
    m = compute_metrics("test", wins=50, losses=50, pushes=0, by_season=by_season)
    assert m.profitable_seasons_pct == pytest.approx(0.5)


def test_profitable_seasons_pct_nan_below_three_seasons():
    from engine.bucket_analysis import compute_metrics
    by_season = {2020: 0.55, 2021: 0.60}
    m = compute_metrics("test", wins=50, losses=40, pushes=0, by_season=by_season)
    assert math.isnan(m.profitable_seasons_pct)


def test_profitable_seasons_pct_nan_empty_by_season():
    from engine.bucket_analysis import compute_metrics
    m = compute_metrics("test", wins=50, losses=40, pushes=0)
    assert math.isnan(m.profitable_seasons_pct)
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_bucket_analysis.py -v -k profitable_seasons
```

Expected: 5 FAIL with `AttributeError: 'BucketMetrics' object has no attribute 'profitable_seasons_pct'`.

- [ ] **Step 3: Modify `engine/bucket_analysis.py`**

Add `math` to imports at the top:

```python
import math
```

Modify the `BucketMetrics` dataclass to add the new field (after `by_season`):

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
    profitable_seasons_pct: float = float("nan")
```

Modify `compute_metrics` — replace the return statement with one that computes `profitable_seasons_pct`. Add this just before the return:

```python
    if by_season and len(by_season) >= 3:
        n_profitable = sum(1 for rate in by_season.values() if rate > BREAKEVEN_AT_NEG_110)
        profitable_seasons_pct = n_profitable / len(by_season)
    else:
        profitable_seasons_pct = math.nan
```

Then add it to the `BucketMetrics(...)` return call:

```python
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
        profitable_seasons_pct=profitable_seasons_pct,
    )
```

Modify `format_table` to add a `prof_seas%` column. Insert in the headers list (after `low_n?`):

```python
    headers = [
        "bucket", "n", "W", "L", "P",
        "win%", "push%", "ROI -110", "ROI -105",
        "p-value", "CI low", "CI high", "low_n?",
        "prof_seas%",
    ]
```

And append to each row's appended list (inside the for-loop, after the `"*"` low-sample marker):

```python
            "—" if math.isnan(r.profitable_seasons_pct) else f"{r.profitable_seasons_pct:.4f}",
```

Modify `write_csv` similarly. Update the header row:

```python
        writer.writerow([
            "bucket", "n", "wins", "losses", "pushes",
            "win_rate", "push_rate", "roi_neg110", "roi_neg105",
            "p_value", "ci_low", "ci_high", "insufficient_sample",
            "by_season",
            "profitable_seasons_pct",
        ])
```

And update each data row (append after the by_season string):

```python
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
                "" if math.isnan(r.profitable_seasons_pct) else f"{r.profitable_seasons_pct:.4f}",
            ])
```

- [ ] **Step 4: Run all bucket_analysis tests + full suite + ruff**

```powershell
uv run pytest tests/test_bucket_analysis.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 5 new tests pass; 227 total (222 prior + 5 new); ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add engine/bucket_analysis.py tests/test_bucket_analysis.py
git commit -m "feat(bucket_analysis): add profitable_seasons_pct metric to BucketMetrics"
```

---

## Task 2: Bootstrap helpers in `engine/stats_utils.py`

**Files:**
- Modify: `engine/stats_utils.py`
- Modify: `tests/test_stats_utils.py`

Purpose: ML buckets have varying payouts per bet (the price isn't uniform across the bucket), so the existing binomial/Wilson tests don't directly apply to "is real_roi > 0". Bootstrap CI + bootstrap p-value handle this cleanly.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_stats_utils.py`:

```python
def test_bootstrap_mean_ci_brackets_known_mean():
    from engine.stats_utils import bootstrap_mean_ci
    # Symmetric pnls around 0.1
    pnls = [0.5, -0.3, 0.4, -0.2, 0.3, -0.1, 0.2, 0.0, 0.2, 0.0]
    lo, hi = bootstrap_mean_ci(pnls, seed=42)
    assert lo < hi
    # Sample mean = 0.10; CI should bracket it
    assert lo < 0.10 < hi


def test_bootstrap_mean_ci_all_positive():
    from engine.stats_utils import bootstrap_mean_ci
    pnls = [0.5, 0.4, 0.3, 0.6, 0.5, 0.4]
    lo, _hi = bootstrap_mean_ci(pnls, seed=42)
    assert lo > 0  # CI lower bound should be positive when all returns positive


def test_bootstrap_mean_ci_empty_raises():
    import pytest
    from engine.stats_utils import bootstrap_mean_ci
    with pytest.raises(ValueError, match="empty"):
        bootstrap_mean_ci([], seed=42)


def test_bootstrap_pvalue_mean_gt_zero_clear_positive():
    from engine.stats_utils import bootstrap_pvalue_mean_gt_zero
    # Strongly positive mean
    pnls = [1.0] * 100
    p = bootstrap_pvalue_mean_gt_zero(pnls, seed=42)
    assert p < 0.01  # essentially zero — no bootstrap sample has mean <= 0


def test_bootstrap_pvalue_mean_gt_zero_clear_negative():
    from engine.stats_utils import bootstrap_pvalue_mean_gt_zero
    pnls = [-1.0] * 100
    p = bootstrap_pvalue_mean_gt_zero(pnls, seed=42)
    assert p > 0.99  # essentially one — every sample has mean <= 0


def test_bootstrap_pvalue_mean_gt_zero_seeded_deterministic():
    from engine.stats_utils import bootstrap_pvalue_mean_gt_zero
    pnls = [0.1, -0.1, 0.2, -0.05, 0.15, -0.08]
    p1 = bootstrap_pvalue_mean_gt_zero(pnls, seed=42)
    p2 = bootstrap_pvalue_mean_gt_zero(pnls, seed=42)
    assert p1 == p2  # deterministic given seed
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_stats_utils.py -v -k bootstrap
```

Expected: 6 FAIL with `ImportError`.

- [ ] **Step 3: Add helpers to `engine/stats_utils.py`**

Append to `engine/stats_utils.py` (after the existing helpers):

```python
def bootstrap_mean_ci(
    values: list[float],
    *,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap 95% CI for the mean of `values`. Returns (ci_low, ci_high).

    Uses naive percentile bootstrap with deterministic seeding. Defaults give
    2.5%/97.5% percentile bounds.
    """
    import random  # local: small fn, avoid module-level dep for code that may not use it

    if not values:
        raise ValueError("bootstrap_mean_ci called with empty values list")
    rng = random.Random(seed)
    n = len(values)
    boots = [sum(rng.choices(values, k=n)) / n for _ in range(n_boot)]
    boots.sort()
    lo_idx = int(n_boot * (alpha / 2))
    hi_idx = int(n_boot * (1 - alpha / 2))
    return boots[lo_idx], boots[hi_idx]


def bootstrap_pvalue_mean_gt_zero(
    values: list[float],
    *,
    n_boot: int = 2000,
    seed: int = 42,
) -> float:
    """Bootstrap p-value for H0: mean(values) <= 0.

    Returns the share of bootstrap resamples whose mean is <= 0.
    p < 0.05 indicates >95% of resamples show a positive mean (i.e., evidence
    that the true mean is positive).
    """
    import random

    if not values:
        raise ValueError("bootstrap_pvalue_mean_gt_zero called with empty values list")
    rng = random.Random(seed)
    n = len(values)
    boots = [sum(rng.choices(values, k=n)) / n for _ in range(n_boot)]
    return sum(1 for b in boots if b <= 0) / n_boot
```

- [ ] **Step 4: Run tests + full suite + ruff**

```powershell
uv run pytest tests/test_stats_utils.py -v -k bootstrap
uv run pytest -q
uv run ruff check .
```

Expected: 6 new tests pass; 233 total; ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add engine/stats_utils.py tests/test_stats_utils.py
git commit -m "feat(stats_utils): bootstrap_mean_ci + bootstrap_pvalue_mean_gt_zero"
```

---

## Task 3: Extend `compare_ml_prices` for per-season + bootstrap stats

**Files:**
- Modify: `engine/validation.py`
- Modify: `tests/test_validation.py`

Purpose: extend `BucketComparison` and `_build_bucket_comparisons` to compute per-season real_roi, bootstrap CI on real_roi, bootstrap p-value, and profitable_seasons_pct. These are what `credible_edges` will rank ML buckets by.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_validation.py`:

```python
def test_compare_ml_prices_bucket_comparison_has_enriched_fields():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")
    report = compare_ml_prices(conn)
    for bc in report.bucket_comparisons:
        assert hasattr(bc, "ci_low")
        assert hasattr(bc, "ci_high")
        assert hasattr(bc, "p_value")
        assert hasattr(bc, "profitable_seasons_pct")
        assert hasattr(bc, "by_season")
        assert bc.ci_low <= bc.real_roi <= bc.ci_high or math.isclose(bc.real_roi, bc.ci_low) or math.isclose(bc.real_roi, bc.ci_high)
    conn.close()


def test_compare_ml_prices_csv_has_new_columns(tmp_path):
    from engine.validation import write_validation_csv

    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _seed_full_fixture(conn)
    load_csv_to_db(conn, "tests/fixtures/real_ml_5.csv")
    report = compare_ml_prices(conn)

    out_path = tmp_path / "validation.csv"
    write_validation_csv(report, out_path)

    text = out_path.read_text(encoding="utf-8")
    assert "ci_low" in text
    assert "ci_high" in text
    assert "p_value" in text
    assert "profitable_seasons_pct" in text
    conn.close()
```

Add `import math` to the top imports block in `tests/test_validation.py` if not already there.

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_validation.py -v -k "enriched_fields or csv_has_new_columns"
```

Expected: 2 FAIL with `AttributeError` (or CSV missing columns).

- [ ] **Step 3: Modify `engine/validation.py`**

Add to the imports block (with other engine imports):

```python
import math

from engine.stats_utils import bootstrap_mean_ci, bootstrap_pvalue_mean_gt_zero
```

Modify the `BucketComparison` dataclass — add five new fields after `losses`:

```python
@dataclass(frozen=True)
class BucketComparison:
    """Per-bucket ROI comparison: derived prices vs real prices, same outcomes.

    `wins` and `losses` are price-invariant — game outcomes don't depend on
    which price you booked the bet at, so we store one pair rather than
    derived_wins/real_wins duplicates.
    """

    bucket: str
    n: int
    derived_roi: float
    real_roi: float
    delta_roi: float
    wins: int
    losses: int
    ci_low: float
    ci_high: float
    p_value: float
    profitable_seasons_pct: float
    by_season: dict[int, float]
```

Modify `compare_ml_prices` to capture season per bet — change the inner loop to include `season`:

```python
    for row in df.itertuples(index=False):
        derived = derive_ml_from_spread(row.spread_home_close)
        if derived is None:
            continue
        derived_home, derived_away = derived
        home_won = row.home_score > row.away_score
        away_won = row.away_score > row.home_score

        for _side_name, derived_ml, real_ml, won in (
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
                    "season": int(row.season),
                    "won": won,
                    "derived_pnl": _payout(derived_ml, won),
                    "real_pnl": _payout(real_ml, won),
                }
            )
```

Modify `_build_bucket_comparisons` to compute the new fields:

```python
def _build_bucket_comparisons(bucket_rows: list[dict]) -> list[BucketComparison]:
    """Aggregate per-bet rows into per-bucket comparison records."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in bucket_rows:
        grouped[row["bucket"]].append(row)
    out: list[BucketComparison] = []
    for bucket, rows in grouped.items():
        n = len(rows)
        wins = sum(1 for r in rows if r["won"])
        losses = sum(1 for r in rows if not r["won"])
        derived_pnls = [r["derived_pnl"] for r in rows]
        real_pnls = [r["real_pnl"] for r in rows]
        derived_roi = sum(derived_pnls) / n
        real_roi = sum(real_pnls) / n

        ci_low, ci_high = bootstrap_mean_ci(real_pnls)
        p_value = bootstrap_pvalue_mean_gt_zero(real_pnls)

        season_groups: dict[int, list[float]] = defaultdict(list)
        for r in rows:
            season_groups[r["season"]].append(r["real_pnl"])
        by_season: dict[int, float] = {
            s: sum(pnls) / len(pnls) for s, pnls in season_groups.items()
        }
        if len(by_season) >= 3:
            n_profitable = sum(1 for roi_s in by_season.values() if roi_s > 0)
            profitable_seasons_pct = n_profitable / len(by_season)
        else:
            profitable_seasons_pct = math.nan

        out.append(
            BucketComparison(
                bucket=bucket,
                n=n,
                derived_roi=derived_roi,
                real_roi=real_roi,
                delta_roi=real_roi - derived_roi,
                wins=wins,
                losses=losses,
                ci_low=ci_low,
                ci_high=ci_high,
                p_value=p_value,
                profitable_seasons_pct=profitable_seasons_pct,
                by_season=by_season,
            )
        )
    out.sort(key=lambda bc: bc.bucket)
    return out
```

Modify the SQL query — it must already include `g.season`. Looking at `_SQL` it does (`SELECT g.game_id, g.season, ...`).

Modify `_format_bucket_table` to show the new columns:

```python
def _format_bucket_table(comparisons: list[BucketComparison]) -> str:
    headers = [
        "bucket", "n",
        "derived_roi", "real_roi", "delta_roi",
        "ci_low", "ci_high", "p_value", "prof_seas%",
        "W", "L",
    ]
    rows = [
        [
            bc.bucket, bc.n,
            f"{bc.derived_roi:+.4f}", f"{bc.real_roi:+.4f}", f"{bc.delta_roi:+.4f}",
            f"{bc.ci_low:+.4f}", f"{bc.ci_high:+.4f}",
            f"{bc.p_value:.4f}",
            "—" if math.isnan(bc.profitable_seasons_pct) else f"{bc.profitable_seasons_pct:.4f}",
            bc.wins, bc.losses,
        ]
        for bc in comparisons
    ]
    return tabulate(rows, headers=headers, tablefmt="github")
```

Modify `write_validation_csv` to include the new columns:

```python
def write_validation_csv(report: ValidationReport, path: str | Path) -> None:
    """Write the bucket-comparison table to CSV with comment-line disclaimer + source note."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Real-line sample: source={report.source}, n_games={report.n_games}",
        f"# {DISCLAIMER}",
        "bucket,n,derived_roi,real_roi,delta_roi,wins,losses,"
        "ci_low,ci_high,p_value,profitable_seasons_pct,by_season",
    ]
    for bc in report.bucket_comparisons:
        prof = "" if math.isnan(bc.profitable_seasons_pct) else f"{bc.profitable_seasons_pct:.4f}"
        season_str = ";".join(f"{s}:{r:.4f}" for s, r in sorted(bc.by_season.items()))
        lines.append(
            f"{bc.bucket},{bc.n},"
            f"{bc.derived_roi:.6f},{bc.real_roi:.6f},{bc.delta_roi:.6f},"
            f"{bc.wins},{bc.losses},"
            f"{bc.ci_low:.6f},{bc.ci_high:.6f},{bc.p_value:.6f},"
            f"{prof},{season_str}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run tests + full suite + ruff**

```powershell
uv run pytest tests/test_validation.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 14 tests pass in this file (12 prior + 2 new); 235 total; ruff clean.

If any existing tests fail due to the new BucketComparison fields being required positional args, that's fine — fix by passing them in any test constructors that exist (search for `BucketComparison(` in tests). Bootstrap is seeded, so test outputs are deterministic.

- [ ] **Step 5: Commit**

```powershell
git add engine/validation.py tests/test_validation.py
git commit -m "feat(validation): ML bucket comparisons get bootstrap CI/p_value/by_season/profitable_seasons_pct"
```

---

## Task 4: `scripts/cross_check_ats_totals.py` — one-time Kaggle-vs-nflverse check

**Files:**
- Create: `scripts/cross_check_ats_totals.py`
- Create: `docs/superpowers/notes/2026-05-28-kaggle-nflverse-crosscheck.md` (will be populated by running the script in T7)

Purpose: verify Kaggle's `spread_home_close` and `total_close` match nflverse's `spread_line` and `total_line` on the 2020–2024 overlap. Outcome drives whether the credible_edges report can use Kaggle's full 2004–2024 ATS/totals data, or must narrow to 2020–2024 nflverse-confirmed.

This script has no tests (one-off exploratory tool; the notes doc is the deliverable).

- [ ] **Step 1: Verify `scripts/` directory exists (or create it)**

```powershell
if (-not (Test-Path scripts)) { New-Item -ItemType Directory -Path scripts | Out-Null }
ls scripts
```

If new, the directory should be empty.

- [ ] **Step 2: Create `scripts/cross_check_ats_totals.py`**

```python
"""One-time Kaggle-vs-nflverse cross-check for closing spread + total lines.

Compares Kaggle's `betting_lines.spread_home_close` and `total_close` to
nflverse's `spread_line` and `total_line` on the 2020-2024 overlap.

Outputs:
  - stdout: agreement %, sample sizes, top 10 worst disagreements per market
  - data/processed/kaggle_vs_nflverse_lines.csv: full per-game comparison

Decision rule for downstream (engine.credible_edges):
  - If spread agreement >= 95% AND total agreement >= 95% → keep Kaggle 2004-2024
  - Else → narrow to 2020-2024 nflverse-confirmed

Run: uv run python scripts/cross_check_ats_totals.py
"""

from __future__ import annotations

from pathlib import Path

import nfl_data_py as nfl
import pandas as pd

from engine.db import connect, fetch_df
from ingestion.team_codes import code_to_canonical

AGREEMENT_TOLERANCE = 0.5  # half-point — anything within this counts as a match
SEASONS = [2020, 2021, 2022, 2023, 2024]
KAGGLE_DB = "data/db/nfl_betting.sqlite"
OUT_CSV = Path("data/processed/kaggle_vs_nflverse_lines.csv")


def main() -> int:
    conn = connect(KAGGLE_DB)
    kaggle = fetch_df(
        conn,
        "SELECT g.season, g.week, g.home_team, g.away_team, "
        "       bl.spread_home_close, bl.total_close "
        "FROM games g JOIN betting_lines bl ON bl.game_id = g.game_id "
        "WHERE g.season BETWEEN 2020 AND 2024",
    )
    conn.close()

    raw = nfl.import_schedules(SEASONS)
    nflv = raw[
        ["season", "week", "home_team", "away_team", "spread_line", "total_line"]
    ].copy()
    nflv["home_team"] = nflv["home_team"].map(code_to_canonical)
    nflv["away_team"] = nflv["away_team"].map(code_to_canonical)
    # nflverse spread_line: positive => home is dog. Kaggle spread_home_close: negative => home is fav.
    # nflverse 9.5 (home dog by 9.5) ≈ Kaggle +9.5; nflverse -3 (home fav by 3) ≈ Kaggle -3.
    # Signs already match.

    merged = kaggle.merge(
        nflv,
        on=["season", "week", "home_team", "away_team"],
        how="inner",
        suffixes=("_kag", "_nfl"),
    )

    n = len(merged)
    if n == 0:
        print("ERROR: zero rows joined — check team-name canonicalization.")
        return 1

    spread_match = (
        (merged["spread_home_close"] - merged["spread_line"]).abs() <= AGREEMENT_TOLERANCE
    )
    total_match = (
        (merged["total_close"] - merged["total_line"]).abs() <= AGREEMENT_TOLERANCE
    )

    spread_pct = spread_match.sum() / n
    total_pct = total_match.sum() / n

    print(f"Matched games: {n}")
    print(f"Spread agreement (±{AGREEMENT_TOLERANCE}): {spread_pct:.4f}")
    print(f"Total  agreement (±{AGREEMENT_TOLERANCE}): {total_pct:.4f}")
    print()

    print("Top 10 worst spread disagreements:")
    worst_spread = (
        merged.assign(spread_diff=lambda d: (d.spread_home_close - d.spread_line).abs())
        .nlargest(10, "spread_diff")
        [["season", "week", "home_team", "away_team", "spread_home_close", "spread_line", "spread_diff"]]
    )
    print(worst_spread.to_string(index=False))
    print()

    print("Top 10 worst total disagreements:")
    worst_total = (
        merged.assign(total_diff=lambda d: (d.total_close - d.total_line).abs())
        .nlargest(10, "total_diff")
        [["season", "week", "home_team", "away_team", "total_close", "total_line", "total_diff"]]
    )
    print(worst_total.to_string(index=False))
    print()

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT_CSV, index=False)
    print(f"Full per-game comparison written to {OUT_CSV}")

    decision = (
        "KEEP Kaggle 2004-2024 for ATS/totals"
        if spread_pct >= 0.95 and total_pct >= 0.95
        else "NARROW to nflverse 2020-2024 for ATS/totals"
    )
    print(f"\nDecision: {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Verify the script imports cleanly (syntax check only — actual run happens in T7)**

```powershell
uv run python -c "import ast; ast.parse(open('scripts/cross_check_ats_totals.py').read()); print('syntax OK')"
```

Expected: `syntax OK`.

- [ ] **Step 4: Run ruff on the new file**

```powershell
uv run ruff check scripts/cross_check_ats_totals.py
```

Expected: clean.

- [ ] **Step 5: Commit**

```powershell
git add scripts/cross_check_ats_totals.py
git commit -m "feat(slice4): cross_check_ats_totals — Kaggle vs nflverse line agreement"
```

(The notes doc is created in T7 with the actual findings.)

---

## Task 5: `engine/credible_edges.py` — pure normalizer + ranker

**Files:**
- Create: `engine/credible_edges.py`
- Create: `tests/test_credible_edges.py`

Purpose: a single pure function `rank_credible_edges(ats_path, totals_path, ml_path) -> list[CredibleEdge]` that reads three CSVs, normalizes them to a common shape, filters by four thresholds, and ranks survivors. CLI added in T6.

- [ ] **Step 1: Write failing tests**

Create `tests/test_credible_edges.py`:

```python
"""Tests for engine.credible_edges — pure ranker tested with synthetic CSVs."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.credible_edges import CredibleEdge, rank_credible_edges


def _write_ats_csv(path: Path, rows: list[dict]) -> None:
    header = (
        "bucket,n,wins,losses,pushes,win_rate,push_rate,roi_neg110,roi_neg105,"
        "p_value,ci_low,ci_high,insufficient_sample,by_season,profitable_seasons_pct"
    )
    lines = ["# disclaimer", header]
    for r in rows:
        lines.append(
            f"{r['bucket']},{r['n']},{r.get('wins', 50)},{r.get('losses', 40)},0,"
            f"{r.get('wins', 50) / (r.get('wins', 50) + r.get('losses', 40)):.6f},0.000000,"
            f"{r['roi']:.6f},{r['roi']:.6f},"
            f"{r['p']:.6f},{r['ci_low']:.6f},{r['ci_high']:.6f},0,"
            f"2020:0.55;2021:0.50;2022:0.60;2023:0.58,"
            f"{r['prof']:.4f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_totals_csv(path: Path, rows: list[dict]) -> None:
    # Same shape as ATS
    _write_ats_csv(path, rows)


def _write_ml_csv(path: Path, rows: list[dict]) -> None:
    header = (
        "bucket,n,derived_roi,real_roi,delta_roi,wins,losses,"
        "ci_low,ci_high,p_value,profitable_seasons_pct,by_season"
    )
    lines = ["# Real-line sample: source=fixture, n_games=100", "# disclaimer", header]
    for r in rows:
        lines.append(
            f"{r['bucket']},{r['n']},0.0,{r['roi']:.6f},0.0,"
            f"{r.get('wins', 50)},{r.get('losses', 40)},"
            f"{r['ci_low']:.6f},{r['ci_high']:.6f},{r['p']:.6f},"
            f"{r['prof']:.4f},2020:0.05;2021:0.01;2022:0.08"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_rank_happy_path(tmp_path):
    ats_path = tmp_path / "ats.csv"
    totals_path = tmp_path / "totals.csv"
    ml_path = tmp_path / "ml.csv"
    _write_ats_csv(
        ats_path,
        [{"bucket": "ats_a", "n": 200, "roi": 0.05, "ci_low": 0.01, "ci_high": 0.09, "p": 0.04, "prof": 0.7}],
    )
    _write_totals_csv(
        totals_path,
        [{"bucket": "tot_a", "n": 300, "roi": 0.03, "ci_low": 0.005, "ci_high": 0.06, "p": 0.08, "prof": 0.65}],
    )
    _write_ml_csv(
        ml_path,
        [{"bucket": "ml_a", "n": 500, "roi": 0.02, "ci_low": 0.015, "ci_high": 0.04, "p": 0.02, "prof": 0.8}],
    )
    edges = rank_credible_edges(ats_path, totals_path, ml_path)
    assert len(edges) == 3
    # Ranked by ci_low desc
    assert edges[0].bucket == "ml_a"   # ci_low 0.015
    assert edges[1].bucket == "ats_a"  # ci_low 0.01
    assert edges[2].bucket == "tot_a"  # ci_low 0.005
    assert all(isinstance(e, CredibleEdge) for e in edges)


def test_rank_rejects_low_n(tmp_path):
    ats = tmp_path / "ats.csv"
    totals = tmp_path / "totals.csv"
    ml = tmp_path / "ml.csv"
    _write_ats_csv(
        ats,
        [{"bucket": "small", "n": 50, "roi": 0.05, "ci_low": 0.02, "ci_high": 0.08, "p": 0.03, "prof": 0.7}],
    )
    _write_totals_csv(totals, [])
    _write_ml_csv(ml, [])
    assert rank_credible_edges(ats, totals, ml) == []


def test_rank_rejects_non_positive_ci_low(tmp_path):
    ats = tmp_path / "ats.csv"
    totals = tmp_path / "totals.csv"
    ml = tmp_path / "ml.csv"
    _write_ats_csv(
        ats,
        [{"bucket": "flat", "n": 200, "roi": 0.0, "ci_low": -0.01, "ci_high": 0.01, "p": 0.5, "prof": 0.5}],
    )
    _write_totals_csv(totals, [])
    _write_ml_csv(ml, [])
    assert rank_credible_edges(ats, totals, ml) == []


def test_rank_rejects_high_p_value(tmp_path):
    ats = tmp_path / "ats.csv"
    totals = tmp_path / "totals.csv"
    ml = tmp_path / "ml.csv"
    _write_ats_csv(
        ats,
        [{"bucket": "noisy", "n": 200, "roi": 0.05, "ci_low": 0.001, "ci_high": 0.10, "p": 0.30, "prof": 0.7}],
    )
    _write_totals_csv(totals, [])
    _write_ml_csv(ml, [])
    assert rank_credible_edges(ats, totals, ml) == []


def test_rank_rejects_low_profitable_seasons(tmp_path):
    ats = tmp_path / "ats.csv"
    totals = tmp_path / "totals.csv"
    ml = tmp_path / "ml.csv"
    _write_ats_csv(
        ats,
        [{"bucket": "spiky", "n": 200, "roi": 0.05, "ci_low": 0.02, "ci_high": 0.08, "p": 0.03, "prof": 0.4}],
    )
    _write_totals_csv(totals, [])
    _write_ml_csv(ml, [])
    assert rank_credible_edges(ats, totals, ml) == []


def test_rank_missing_csv_raises(tmp_path):
    ats = tmp_path / "missing_ats.csv"
    totals = tmp_path / "missing_totals.csv"
    ml = tmp_path / "missing_ml.csv"
    with pytest.raises(FileNotFoundError):
        rank_credible_edges(ats, totals, ml)
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_credible_edges.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `engine/credible_edges.py`**

```python
"""Cross-market credible-edges ranker.

Reads the three per-market reports (ATS, totals, moneyline-validation),
filters each bucket by four credibility thresholds, ranks survivors by
Wilson lower bound (descending), and outputs a single CSV.

The thresholds defining a "credible" edge:
  - n >= 100               (sample size floor)
  - ci_low > 0             (95% confident the true edge is positive)
  - p_value < 0.10         (modest evidence vs breakeven)
  - profitable_seasons_pct >= 0.60   (stable across time)

For ML buckets, `roi` is the real_roi from Slice 3 — derived prices are
biased per the Slice 3 finding.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

MIN_N = 100
MIN_CI_LOW = 0.0  # strict-positive: ci_low > 0
MAX_P_VALUE = 0.10
MIN_PROFITABLE_SEASONS_PCT = 0.60


@dataclass(frozen=True)
class CredibleEdge:
    market: str
    bucket: str
    n: int
    roi: float
    ci_low: float
    ci_high: float
    p_value: float
    profitable_seasons_pct: float


def _read_csv_skipping_comments(path: Path) -> list[dict]:
    """Read a CSV that may have one or more leading # comment lines.

    Returns list of row-dicts using the first non-# line as the header.
    """
    if not path.exists():
        raise FileNotFoundError(f"required CSV not found: {path}")
    with path.open(encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    return list(reader)


def _parse_float_or_nan(value: str) -> float:
    if value is None or value.strip() == "":
        return math.nan
    return float(value)


def _normalize_ats_or_totals(market: str, row: dict) -> dict:
    return {
        "market": market,
        "bucket": row["bucket"],
        "n": int(row["n"]),
        "roi": _parse_float_or_nan(row["roi_neg110"]),
        "ci_low": _parse_float_or_nan(row["ci_low"]),
        "ci_high": _parse_float_or_nan(row["ci_high"]),
        "p_value": _parse_float_or_nan(row["p_value"]),
        "profitable_seasons_pct": _parse_float_or_nan(row["profitable_seasons_pct"]),
    }


def _normalize_ml(row: dict) -> dict:
    return {
        "market": "ml",
        "bucket": row["bucket"],
        "n": int(row["n"]),
        "roi": _parse_float_or_nan(row["real_roi"]),
        "ci_low": _parse_float_or_nan(row["ci_low"]),
        "ci_high": _parse_float_or_nan(row["ci_high"]),
        "p_value": _parse_float_or_nan(row["p_value"]),
        "profitable_seasons_pct": _parse_float_or_nan(row["profitable_seasons_pct"]),
    }


def _passes(norm: dict) -> bool:
    if norm["n"] < MIN_N:
        return False
    if math.isnan(norm["ci_low"]) or norm["ci_low"] <= MIN_CI_LOW:
        return False
    if math.isnan(norm["p_value"]) or norm["p_value"] >= MAX_P_VALUE:
        return False
    if math.isnan(norm["profitable_seasons_pct"]) or norm["profitable_seasons_pct"] < MIN_PROFITABLE_SEASONS_PCT:
        return False
    return True


def rank_credible_edges(
    ats_path: str | Path,
    totals_path: str | Path,
    ml_path: str | Path,
) -> list[CredibleEdge]:
    """Read 3 per-market CSVs, filter by credibility thresholds, rank by ci_low desc."""
    ats_rows = [_normalize_ats_or_totals("ats", r) for r in _read_csv_skipping_comments(Path(ats_path))]
    tot_rows = [_normalize_ats_or_totals("totals", r) for r in _read_csv_skipping_comments(Path(totals_path))]
    ml_rows = [_normalize_ml(r) for r in _read_csv_skipping_comments(Path(ml_path))]

    survivors = [r for r in (ats_rows + tot_rows + ml_rows) if _passes(r)]
    survivors.sort(key=lambda r: r["ci_low"], reverse=True)
    return [
        CredibleEdge(
            market=r["market"],
            bucket=r["bucket"],
            n=r["n"],
            roi=r["roi"],
            ci_low=r["ci_low"],
            ci_high=r["ci_high"],
            p_value=r["p_value"],
            profitable_seasons_pct=r["profitable_seasons_pct"],
        )
        for r in survivors
    ]
```

- [ ] **Step 4: Run tests + full suite + ruff**

```powershell
uv run pytest tests/test_credible_edges.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 6 new tests pass; 241 total; ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add engine/credible_edges.py tests/test_credible_edges.py
git commit -m "feat(credible_edges): cross-market ranker (4 thresholds, Wilson-low desc)"
```

---

## Task 6: `engine/credible_edges.py` — CLI + CSV writer

**Files:**
- Modify: `engine/credible_edges.py` (append `write_credible_edges_csv` + `_main`)
- Modify: `tests/test_credible_edges.py` (append CSV writer test)

Purpose: human-readable stdout table + CSV output with comment-line disclaimer + threshold note.

- [ ] **Step 1: Write failing test**

Append to `tests/test_credible_edges.py`:

```python
def test_write_credible_edges_csv_includes_threshold_note(tmp_path):
    from engine.credible_edges import CredibleEdge, write_credible_edges_csv

    edges = [
        CredibleEdge(
            market="ats",
            bucket="ats_a",
            n=200,
            roi=0.05,
            ci_low=0.01,
            ci_high=0.09,
            p_value=0.04,
            profitable_seasons_pct=0.7,
        ),
    ]
    out_path = tmp_path / "credible_edges.csv"
    write_credible_edges_csv(edges, out_path)
    text = out_path.read_text(encoding="utf-8")
    assert "# Credible-edge thresholds:" in text
    assert "n>=100" in text
    assert "# Past performance" in text
    assert "market,bucket,n,roi,ci_low,ci_high,p_value,profitable_seasons_pct" in text
    assert "ats,ats_a,200" in text


def test_write_credible_edges_csv_empty(tmp_path):
    from engine.credible_edges import write_credible_edges_csv

    out_path = tmp_path / "credible_edges_empty.csv"
    write_credible_edges_csv([], out_path)
    text = out_path.read_text(encoding="utf-8")
    # header still present, but no data rows
    assert "market,bucket,n,roi" in text
    data_lines = [ln for ln in text.splitlines() if not ln.startswith("#") and "market" not in ln and ln.strip()]
    assert data_lines == []
```

- [ ] **Step 2: Run tests, verify they fail**

```powershell
uv run pytest tests/test_credible_edges.py -v -k write_credible_edges_csv
```

Expected: `ImportError`.

- [ ] **Step 3: Append CLI + writer to `engine/credible_edges.py`**

Add to the imports block:

```python
from tabulate import tabulate

from engine.bucket_analysis import DISCLAIMER
```

Append after `rank_credible_edges`:

```python
DEFAULT_ATS_CSV = "data/processed/ats_by_bucket.csv"
DEFAULT_TOTALS_CSV = "data/processed/totals_by_bucket.csv"
DEFAULT_ML_CSV = "data/processed/ml_validation_report.csv"
DEFAULT_OUT_CSV = "data/processed/credible_edges.csv"

_THRESHOLD_NOTE = (
    f"# Credible-edge thresholds: n>={MIN_N}, ci_low>{MIN_CI_LOW}, "
    f"p<{MAX_P_VALUE}, profitable_seasons>={MIN_PROFITABLE_SEASONS_PCT}. "
    f"Ranked by ci_low desc."
)


def _format_edges_table(edges: list[CredibleEdge]) -> str:
    headers = ["market", "bucket", "n", "roi", "ci_low", "ci_high", "p_value", "prof_seas%"]
    rows = [
        [
            e.market, e.bucket, e.n,
            f"{e.roi:+.4f}",
            f"{e.ci_low:+.4f}",
            f"{e.ci_high:+.4f}",
            f"{e.p_value:.4f}",
            f"{e.profitable_seasons_pct:.4f}",
        ]
        for e in edges
    ]
    return tabulate(rows, headers=headers, tablefmt="github")


def write_credible_edges_csv(edges: list[CredibleEdge], path: str | Path) -> None:
    """Write the ranked credible-edges to CSV with threshold note + disclaimer."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        _THRESHOLD_NOTE,
        f"# {DISCLAIMER}",
        "market,bucket,n,roi,ci_low,ci_high,p_value,profitable_seasons_pct",
    ]
    for e in edges:
        lines.append(
            f"{e.market},{e.bucket},{e.n},"
            f"{e.roi:.6f},{e.ci_low:.6f},{e.ci_high:.6f},"
            f"{e.p_value:.6f},{e.profitable_seasons_pct:.4f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _main() -> int:
    """CLI: uv run python -m engine.credible_edges"""
    try:
        edges = rank_credible_edges(DEFAULT_ATS_CSV, DEFAULT_TOTALS_CSV, DEFAULT_ML_CSV)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Hint: run `uv run python -m engine.ats`, `uv run python -m engine.totals`, "
              "and `uv run python -m engine.validation` first.")
        return 1

    if not edges:
        print("No buckets meet credibility thresholds.")
        print(_THRESHOLD_NOTE[2:])  # strip leading "# "
    else:
        print(f"Credible edges across all 3 markets ({len(edges)} survivors):\n")
        print(_format_edges_table(edges))

    write_credible_edges_csv(edges, DEFAULT_OUT_CSV)
    print(f"\n{DISCLAIMER}")
    print(f"\nCSV written to {DEFAULT_OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
```

- [ ] **Step 4: Run tests + full suite + ruff**

```powershell
uv run pytest tests/test_credible_edges.py -v
uv run pytest -q
uv run ruff check .
```

Expected: 8 tests pass in this file (6 prior + 2 new); 243 total; ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add engine/credible_edges.py tests/test_credible_edges.py
git commit -m "feat(credible_edges): CLI + CSV writer with threshold note + disclaimer"
```

---

## Task 7: Real-data run — cross-check, refresh CSVs, generate credible_edges

**Files:**
- Create: `docs/superpowers/notes/2026-05-28-kaggle-nflverse-crosscheck.md` (with actual findings)

Assumes Slices 1–3 outputs already exist (Kaggle loaded into `data/db/nfl_betting.sqlite`, nflverse real-ML loaded into `real_ml_lines`).

- [ ] **Step 1: Run the cross-check script**

```powershell
uv run python scripts/cross_check_ats_totals.py
```

Expected output: agreement %, top 10 worst disagreements per market, decision line. Capture the output — it goes into the notes doc in Step 2.

If `data/processed/kaggle_vs_nflverse_lines.csv` is not written, investigate. Most likely cause: zero rows joined → team-name canonicalization issue.

- [ ] **Step 2: Write the findings doc**

Create `docs/superpowers/notes/2026-05-28-kaggle-nflverse-crosscheck.md` with the actual numbers (fill in from Step 1 output):

```markdown
# Kaggle vs nflverse closing-line cross-check — 2026-05-28

**Window:** 2020–2024 (5 seasons)
**Tolerance:** ±0.5 (half-point)

## Results

| Metric | Value |
|---|---|
| Matched games | N |
| Spread agreement | X.XXXX |
| Total agreement | X.XXXX |

## Decision

Spread agreement = X.XX% and total agreement = X.XX%.

→ (KEEP Kaggle 2004-2024 / NARROW to nflverse 2020-2024) — fill in per actual decision.

## Top 5 worst spread disagreements

(paste from script output, trimmed)

## Top 5 worst total disagreements

(paste from script output, trimmed)
```

- [ ] **Step 3: Re-run per-market CLIs to refresh CSVs with profitable_seasons_pct column**

```powershell
uv run python -m engine.ats 2>&1 | tail -5
uv run python -m engine.totals 2>&1 | tail -5
uv run python -m engine.validation 2>&1 | tail -5
```

Verify each prints a successful summary and writes its CSV. Spot-check that the new `profitable_seasons_pct` column shows up:

```powershell
Get-Content data/processed/ats_by_bucket.csv -TotalCount 2 | Select-Object -Last 1
Get-Content data/processed/totals_by_bucket.csv -TotalCount 2 | Select-Object -Last 1
Get-Content data/processed/ml_validation_report.csv -TotalCount 3 | Select-Object -Last 1
```

Expected: each header line includes `profitable_seasons_pct` (and the ML one also includes `ci_low,ci_high,p_value`).

- [ ] **Step 4: Run the credible_edges CLI**

```powershell
uv run python -m engine.credible_edges
```

Expected: either a tabulated table of N surviving buckets, or "No buckets meet credibility thresholds." Either is a valid outcome. Save the printed output — it becomes the headline finding for the README in T8.

- [ ] **Step 5: Spot-check CSV**

```powershell
Get-Content data/processed/credible_edges.csv -TotalCount 5
```

Expected: line 1 = threshold note, line 2 = disclaimer, line 3 = header, line 4+ = data (or empty).

- [ ] **Step 6: Final test + ruff sweep**

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: 243 tests pass, ruff clean.

- [ ] **Step 7: Commit the findings doc**

```powershell
git add docs/superpowers/notes/2026-05-28-kaggle-nflverse-crosscheck.md
git commit -m "docs(slice4): Kaggle-vs-nflverse cross-check findings"
```

(The data CSVs at `data/processed/*` are gitignored.)

---

## Task 8: README + memory entry + tag `slice4-complete`

**Files:**
- Modify: `README.md`
- Modify: `.wolf/memory.md`

- [ ] **Step 1: Add a "Slice 4 — credible edges" section to README**

Open `README.md`. Replace the existing `## Scope` block with the following (which adds Slice 4 above scope and updates the bullet list):

Insert a new section ABOVE `## Scope`:

```markdown
## Slice 4 — Credible-edge ranker

Adds Wilson CI / p-value / per-season stability to all three markets and produces a unified ranked report of buckets meeting four credibility thresholds.

### Run

    # (one-time) verify Kaggle ATS/totals lines match nflverse on the 2020-2024 overlap
    uv run python scripts/cross_check_ats_totals.py

    # refresh per-market reports with new profitable_seasons_pct column
    uv run python -m engine.ats
    uv run python -m engine.totals
    uv run python -m engine.validation

    # rank credible edges across all 3 markets
    uv run python -m engine.credible_edges

### Credibility thresholds

A bucket qualifies if ALL of:
- `n >= 100`
- `ci_low > 0` (95% CI lower bound strictly positive)
- `p_value < 0.10`
- `profitable_seasons_pct >= 0.60`

Survivors are ranked by `ci_low` (descending) — most conservative true-edge estimate first.

For ML buckets, `roi` is real-line ROI from nflverse, not derived (Slice 3 showed derived is biased).

### Headline finding

Fill in from T7 output. Example: "N buckets cleared all thresholds. Top edge: market=X, bucket=Y, n=Z, ci_low=+0.0AB." Or: "No buckets cleared all four thresholds — the NFL market is too efficient for static bucket-betting strategies in this sample window."
```

Update the `## Scope` block by changing the existing bullets and adding Slice 4:

```markdown
## Scope

- **Slice 1 (complete):** ingestion, schema, statistics utilities, ATS-by-spread-bucket analysis.
- **Slice 2 (complete):** totals-by-line-bucket and moneyline-by-odds-bucket analysis (ML prices derived from spreads).
- **Slice 3 (complete):** real-line moneyline validation against nflverse 2020–2024. Heavy-fav +0.63% finding killed; small-fav real-line edge surfaced for follow-up.
- **Slice 4 (complete):** real-line statistical workup across all 3 markets; unified credible-edge ranker.
- **Deferred to later slices:** live odds ingestion, this-week pick generator, backtest framework, interactive dashboard.
```

Also update the opening line "Slices 1–3" → "Slices 1–4".

- [ ] **Step 2: Commit README**

```powershell
git add README.md
git commit -m "docs(readme): Slice 4 credible-edges workflow + headline finding"
```

- [ ] **Step 3: Append finding to `.wolf/memory.md`**

Add a one-line entry under the current session header (fill in actual outcome from T7):

```
| HH:MM | Slice 4 finding: N buckets cleared credibility thresholds (n>=100, ci_low>0, p<0.10, prof_seas>=0.60). Top edge market=X bucket=Y ci_low=+0.0AB. (OR: No buckets cleared — NFL market too efficient for static bucket strategies in this window.) | data/processed/credible_edges.csv | ~tokens |
```

- [ ] **Step 4: Commit memory.md update**

```powershell
git add .wolf/memory.md
git commit -m "chore(wolf): record Slice 4 credible-edges findings"
```

- [ ] **Step 5: Confirm clean tree**

```powershell
git status
```

If `.wolf/*` files (anatomy/buglog/cerebrum/token-ledger/hooks-session) show as modified — they get auto-updated by hooks — stage and commit them in one final chore commit:

```powershell
git add .wolf/
git commit -m "chore(wolf): session logs through Slice 4 completion"
```

- [ ] **Step 6: Tag the slice**

```powershell
git tag -a slice4-complete -m "Slice 4: real-line statistical workup + credible-edge ranker"
git tag
```

Expected: `slice1-complete`, `slice2-complete`, `slice3-complete`, `slice4-complete` all listed.

---

## Slice 4 — Definition of Done checklist

- [ ] `BucketMetrics.profitable_seasons_pct` field exists; `compute_metrics` computes it correctly (5 unit tests)
- [ ] `engine/stats_utils` has `bootstrap_mean_ci` + `bootstrap_pvalue_mean_gt_zero` (6 tests, seeded)
- [ ] `compare_ml_prices` produces ML `BucketComparison` with ci_low/ci_high/p_value/profitable_seasons_pct/by_season (2 new tests)
- [ ] Re-running `engine.ats`, `engine.totals`, `engine.validation` produces CSVs that include the new column(s)
- [ ] `scripts/cross_check_ats_totals.py` runs against real data; findings doc captures spread/total agreement % + decision
- [ ] `engine/credible_edges.py` + CLI exists; produces `data/processed/credible_edges.csv` with threshold note + disclaimer
- [ ] `tests/test_credible_edges.py` ≥ 8 passing tests
- [ ] `uv run pytest -q` ~243 tests passing
- [ ] `uv run ruff check .` clean
- [ ] Full pipeline runs end-to-end producing a result (non-empty OR explicitly empty with helpful message)
- [ ] README updated with Slice 4 section + headline finding
- [ ] `.wolf/memory.md` finding entry
- [ ] Tag `slice4-complete` cut
