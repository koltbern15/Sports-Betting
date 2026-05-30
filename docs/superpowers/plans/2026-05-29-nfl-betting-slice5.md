# NFL Betting Analytics — Slice 5: Honest Edge Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the binary "credible edges" filter with an honest edge report that shows every bucket ranked by point-estimate ROI and annotated with two power columns (`mde80_roi`, `breakeven_needed_roi`), and fix the derived-moneyline clamp bug that produces absurd prices at steep spreads.

**Architecture:** Approach A from the spec — repurpose `engine/credible_edges.py` in place, renaming it to `engine/edge_report.py` and its output to `data/processed/edge_report.csv`. The existing CSV normalization is reused; the filter-and-drop step is replaced with measure-and-annotate (no rows dropped). All new statistics live as pure, golden-tested helpers in `engine/stats_utils.py`. The bug fix is a localized change to `engine/moneyline.derive_ml_from_spread`.

**Tech Stack:** Python 3, `scipy.stats` (already a dep), `tabulate`, `pytest`, `uv`, `ruff`.

**Note on spec refinement:** the spec described "two helpers." The honest implementation is **six small pure functions** (two power concepts × two distributions, plus a win-rate→ROI converter and a std-reconstruction helper). This is better-factored and each function is independently golden-testable. The two *report columns* the spec promised (`mde80_roi`, `breakeven_needed_roi`) are unchanged. The ML power columns need a per-bet PnL standard deviation that the ML validation CSV does not carry; rather than expand scope into `validation.py`, `std_from_mean_ci` reconstructs it from the bootstrap CI half-width (documented normal-theory approximation).

**Constants used throughout (one-sided power test at α=0.10, power=0.80; 95% two-sided CI):**
- `z_α = norm.ppf(0.90) ≈ 1.281552`
- `z_β = norm.ppf(0.80) ≈ 0.841621`
- `z_{0.975} = norm.ppf(0.975) ≈ 1.959964`
- breakeven win rate at −110: `BREAKEVEN_AT_NEG_110 = 110/210 ≈ 0.523810` (already defined in `stats_utils`)
- profit per win at −110: `american_to_decimal(-110) − 1 ≈ 0.909091`

---

## File structure

| File | Responsibility | Lifecycle |
|---|---|---|
| `engine/stats_utils.py` | Add 6 pure functions: `roi_from_win_prob`, `mde_winrate_at_power`, `winrate_needed_for_ci`, `mde_mean_at_power`, `mean_needed_for_ci`, `std_from_mean_ci`. | MODIFY |
| `tests/test_stats_utils.py` | Golden-value tests for the 6 new functions. | MODIFY |
| `engine/moneyline.py` | Fix the implied-probability clamp in `derive_ml_from_spread`. | MODIFY |
| `tests/test_moneyline.py` | Regression test: steep spread yields a sane price (≥ −10000). | MODIFY |
| `engine/credible_edges.py` → `engine/edge_report.py` | Rename. Replace filter with measure-and-annotate; emit the new schema; rank by `point_roi` desc. | RENAME + REWRITE |
| `tests/test_credible_edges.py` → `tests/test_edge_report.py` | Rename. Rewrite assertions for no-drop + ranking + power columns. | RENAME + REWRITE |
| `data/processed/credible_edges.csv` | Delete (replaced by `edge_report.csv`, produced by the pipeline run). | DELETE |
| `README.md` | Replace the Slice 4 "credible-edge" section with the Slice 5 honest-report framing. | MODIFY |
| `scripts/cross_check_ats_totals.py` | Update the one stale `engine.credible_edges` reference in a comment. | MODIFY |

---

## Task 1: Statistics helpers in `stats_utils.py`

**Files:**
- Modify: `engine/stats_utils.py` (append after `bootstrap_pvalue_mean_gt_zero`, end of file ~line 164)
- Test: `tests/test_stats_utils.py` (append new tests; imports at top, lines 1-5)

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/test_stats_utils.py`. First add the new names to the existing `from engine.stats_utils import (...)` block at line 5 (add `roi_from_win_prob`, `mde_winrate_at_power`, `winrate_needed_for_ci`, `mde_mean_at_power`, `mean_needed_for_ci`, `std_from_mean_ci`). Then append:

```python
def test_roi_from_win_prob_breakeven_is_zero():
    # 110/210 win rate at -110 is exactly breakeven → ROI 0
    assert roi_from_win_prob(110 / 210, -110) == pytest.approx(0.0, abs=1e-9)


def test_roi_from_win_prob_55_pct():
    # 0.55 * 0.909091 - 0.45 = 0.04999...
    assert roi_from_win_prob(0.55, -110) == pytest.approx(0.05, abs=1e-4)


def test_roi_from_win_prob_propagates_nan():
    assert math.isnan(roi_from_win_prob(float("nan")))


def test_mde_winrate_at_power_n100():
    # At n=100 a static edge must be ~62.8% win rate (~+20% ROI) to be 80%-power
    # detectable vs the -110 breakeven. (Matches the audit's power table.)
    p1 = mde_winrate_at_power(100)
    assert 0.62 < p1 < 0.64
    assert roi_from_win_prob(p1) == pytest.approx(0.20, abs=0.02)


def test_mde_winrate_at_power_n500():
    p1 = mde_winrate_at_power(500)
    assert 0.565 < p1 < 0.575
    assert roi_from_win_prob(p1) == pytest.approx(0.084, abs=0.02)


def test_mde_winrate_at_power_shrinks_with_n():
    # More samples → smaller detectable edge
    assert mde_winrate_at_power(1000) < mde_winrate_at_power(100)


def test_mde_winrate_at_power_zero_n_is_nan():
    assert math.isnan(mde_winrate_at_power(0))


def test_winrate_needed_for_ci_is_boundary():
    # The returned win rate's Wilson lower bound clears breakeven, and one fewer
    # win does not. Tests the inversion is exact, not off-by-one.
    n = 500
    p0 = 110 / 210
    p_needed = winrate_needed_for_ci(n, p0)
    w = round(p_needed * n)
    lo_at, _ = wilson_ci(w, n)
    lo_below, _ = wilson_ci(w - 1, n)
    assert lo_at > p0
    assert lo_below <= p0


def test_winrate_needed_for_ci_zero_n_is_nan():
    assert math.isnan(winrate_needed_for_ci(0))


def test_mde_mean_at_power_closed_form():
    # (z_a + z_b) * std / sqrt(n) = (1.281552 + 0.841621) * 1.0 / 20 = 0.106159
    assert mde_mean_at_power(400, 1.0) == pytest.approx(0.106159, abs=1e-4)


def test_mde_mean_at_power_bad_input_is_nan():
    assert math.isnan(mde_mean_at_power(0, 1.0))
    assert math.isnan(mde_mean_at_power(400, float("nan")))


def test_mean_needed_for_ci_closed_form():
    # z_{0.975} * std / sqrt(n) = 1.959964 * 1.0 / 20 = 0.097998
    assert mean_needed_for_ci(400, 1.0) == pytest.approx(0.097998, abs=1e-4)


def test_std_from_mean_ci_roundtrips_mean_needed():
    # A symmetric 95% CI of half-width 0.097998 at n=400 implies std=1.0
    std = std_from_mean_ci(-0.097998, 0.097998, 400)
    assert std == pytest.approx(1.0, abs=1e-3)


def test_std_from_mean_ci_bad_input_is_nan():
    assert math.isnan(std_from_mean_ci(float("nan"), 0.1, 400))
    assert math.isnan(std_from_mean_ci(-0.1, 0.1, 0))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stats_utils.py -q`
Expected: FAIL / ImportError — the six new names don't exist yet.

- [ ] **Step 3: Implement the six helpers**

Append to `engine/stats_utils.py` (after line 164, end of file). `math` and `_norm` are already imported at the top.

```python
def roi_from_win_prob(p: float, american_odds: int = -110) -> float:
    """Expected ROI per 1-unit bet for a true win probability `p` at given odds.

    roi = p * profit_per_win - (1 - p). At -110, p = 110/210 returns 0.
    Propagates NaN (so callers can pass through unsolved power estimates).
    """
    if p != p:  # NaN
        return math.nan
    profit_per_win = american_to_decimal(american_odds) - 1.0
    return p * profit_per_win - (1.0 - p)


def mde_winrate_at_power(
    n: int,
    p0: float = BREAKEVEN_AT_NEG_110,
    *,
    alpha: float = 0.10,
    power: float = 0.80,
) -> float:
    """Smallest TRUE win rate p1 > p0 detectable at `power`, one-sided level `alpha`,
    given n decided bets. Normal approximation; solved numerically.

    Solves  n = (z_a*sqrt(p0*q0) + z_b*sqrt(p1*q1))**2 / (p1 - p0)**2  for p1.
    required_n(p1) is monotonically decreasing on (p0, 1): a larger true effect
    needs fewer samples. Returns NaN if n <= 0 or n is too small to detect any
    p1 < 1 (i.e. required_n at p1≈1 still exceeds n).
    """
    if n <= 0:
        return math.nan
    z_a = _norm.ppf(1.0 - alpha)
    z_b = _norm.ppf(power)

    def required_n(p1: float) -> float:
        se0 = math.sqrt(p0 * (1.0 - p0))
        se1 = math.sqrt(p1 * (1.0 - p1))
        return (z_a * se0 + z_b * se1) ** 2 / (p1 - p0) ** 2

    lo, hi = p0 + 1e-9, 1.0 - 1e-9
    if required_n(hi) > n:
        return math.nan
    # Invariant: required_n(lo) > n, required_n(hi) <= n. Bisect for the crossing.
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if required_n(mid) > n:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def winrate_needed_for_ci(
    n: int,
    p0: float = BREAKEVEN_AT_NEG_110,
    *,
    alpha: float = 0.05,
) -> float:
    """Smallest observed win rate whose Wilson (1-alpha) CI lower bound exceeds p0,
    given n decided bets. Wilson lower bound is monotone increasing in wins, so the
    first qualifying win count is the minimum. Returns NaN if n <= 0 or unattainable.
    """
    if n <= 0:
        return math.nan
    for w in range(0, n + 1):
        lo, _hi = wilson_ci(w, n, alpha)
        if lo > p0:
            return w / n
    return math.nan


def mde_mean_at_power(
    n: int,
    std: float,
    *,
    alpha: float = 0.10,
    power: float = 0.80,
) -> float:
    """Smallest TRUE mean (vs null 0) detectable at `power`, one-sided level `alpha`,
    for n observations with per-observation std `std`.  mde = (z_a + z_b)*std/sqrt(n).
    Returns NaN on n <= 0 or non-finite/negative std.
    """
    if n <= 0 or std != std or std < 0:
        return math.nan
    z_a = _norm.ppf(1.0 - alpha)
    z_b = _norm.ppf(power)
    return (z_a + z_b) * std / math.sqrt(n)


def mean_needed_for_ci(
    n: int,
    std: float,
    *,
    alpha: float = 0.05,
) -> float:
    """Smallest observed mean whose normal-theory (1-alpha) CI lower bound exceeds 0,
    given n observations with per-observation std `std`.  needed = z*std/sqrt(n),
    z = norm.ppf(1 - alpha/2). Returns NaN on n <= 0 or non-finite/negative std.
    """
    if n <= 0 or std != std or std < 0:
        return math.nan
    z = _norm.ppf(1.0 - alpha / 2.0)
    return z * std / math.sqrt(n)


def std_from_mean_ci(
    ci_low: float,
    ci_high: float,
    n: int,
    *,
    alpha: float = 0.05,
) -> float:
    """Reconstruct per-observation std from a (1-alpha) normal-theory mean CI.

    Inverse of  mean ± z*std/sqrt(n).  Used to recover std when only the CI is
    available (e.g. a bootstrap CI persisted in a CSV). Approximation: assumes the
    interval is symmetric and normal-theory. Returns NaN on bad input.
    """
    if n <= 0 or ci_low != ci_low or ci_high != ci_high:
        return math.nan
    half = (ci_high - ci_low) / 2.0
    z = _norm.ppf(1.0 - alpha / 2.0)
    return half * math.sqrt(n) / z
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stats_utils.py -q`
Expected: PASS (all prior + 14 new).

- [ ] **Step 5: Lint**

Run: `uv run ruff check engine/stats_utils.py tests/test_stats_utils.py`
Expected: clean (no errors).

- [ ] **Step 6: Commit**

```bash
git add engine/stats_utils.py tests/test_stats_utils.py
git commit -m "feat(stats_utils): power/MDE helpers for honest edge report

mde_winrate_at_power, winrate_needed_for_ci, mde_mean_at_power,
mean_needed_for_ci, std_from_mean_ci, roi_from_win_prob — all pure,
golden-value tested.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Fix the derived-moneyline clamp bug

**Files:**
- Modify: `engine/moneyline.py:29` (constant), `engine/moneyline.py:56-57` (clamp)
- Test: `tests/test_moneyline.py` (append after the extreme-spread test, ~line 59)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_moneyline.py` (after `test_derive_ml_from_spread_does_not_crash_on_extreme_spreads`, ~line 59). The import block already has `from engine.moneyline import (...)` at line 10 — add `_payout_for_bet` to it.

```python
def test_derive_ml_steep_spread_price_floors_near_minus_10000():
    """Bug fix: at spreads steeper than ~-24 the proportional vig pushed implied
    prob above 1.0, producing -99,999,900. The price must now floor near -10000."""
    ml_home, ml_away = derive_ml_from_spread(-26.5)
    assert ml_home >= -10000, f"home price too extreme: {ml_home}"
    # A winning heavy-fav bet must pay a realistic (small but non-trivial) amount,
    # not ~0.000001 as the old -99,999,900 price produced.
    assert _payout_for_bet(ml_home, True) > 0.001
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_moneyline.py::test_derive_ml_steep_spread_price_floors_near_minus_10000 -v`
Expected: FAIL — current code returns `ml_home == -99999900`, so `_payout_for_bet` ≈ 1e-6, failing the `> 0.001` assertion.

- [ ] **Step 3: Implement the fix**

In `engine/moneyline.py`, replace the `_EPS` constant at line 29:

```python
_EPS = 1e-6
```

with:

```python
# Proportional vig (p_novig * overround) can push a heavy favorite's implied
# probability above 1.0 at spreads steeper than ~-24, which previously produced
# absurd prices like -99,999,900. Clamp the vigged implied probability to the band
# that maps to +/-10000 American so heavy-fav payouts stay realistic.
_MAX_IMPLIED_PROB = 10000 / 10100  # -> -10000 American
_MIN_IMPLIED_PROB = 100 / 10100    # -> +10000 American
```

Then replace lines 56-57:

```python
    p_home_vig = min(max(p_home_nv * TARGET_OVERROUND, _EPS), 1.0 - _EPS)
    p_away_vig = min(max(p_away_nv * TARGET_OVERROUND, _EPS), 1.0 - _EPS)
```

with:

```python
    p_home_vig = min(max(p_home_nv * TARGET_OVERROUND, _MIN_IMPLIED_PROB), _MAX_IMPLIED_PROB)
    p_away_vig = min(max(p_away_nv * TARGET_OVERROUND, _MIN_IMPLIED_PROB), _MAX_IMPLIED_PROB)
```

- [ ] **Step 4: Run the new test + the existing moneyline suite to verify pass + no regression**

Run: `uv run pytest tests/test_moneyline.py -q`
Expected: PASS — the new test passes and all existing tests (including `test_derive_ml_from_spread_reference_values` and the no-crash test) still pass. The reference values at spreads −3/−7/−14 are well inside the clamp band and are unaffected.

- [ ] **Step 5: Lint**

Run: `uv run ruff check engine/moneyline.py tests/test_moneyline.py`
Expected: clean. (`_EPS` is fully removed, so no unused-constant concern.)

- [ ] **Step 6: Commit**

```bash
git add engine/moneyline.py tests/test_moneyline.py
git commit -m "fix(moneyline): clamp derived price to +/-10000, not -99,999,900

Proportional vig drove implied prob above 1.0 at spreads steeper than
~-24, silently understating ml_heavy_fav payouts. Cap the implied prob
to the band mapping to +/-10000 American.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Rename `credible_edges` → `edge_report` and rewrite to measure-and-annotate

**Files:**
- Rename: `engine/credible_edges.py` → `engine/edge_report.py`
- Rename: `tests/test_credible_edges.py` → `tests/test_edge_report.py`
- Rewrite both (full new contents below).

- [ ] **Step 1: Rename both files with git (preserves history)**

```bash
git mv engine/credible_edges.py engine/edge_report.py
git mv tests/test_credible_edges.py tests/test_edge_report.py
```

- [ ] **Step 2: Write the new failing tests**

Replace the entire contents of `tests/test_edge_report.py` with:

```python
"""Tests for engine.edge_report — pure measure-and-annotate report, synthetic CSVs."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from engine.edge_report import EdgeRow, build_edge_report, write_edge_report_csv


def _write_ats_csv(path: Path, rows: list[dict]) -> None:
    header = (
        "bucket,n,wins,losses,pushes,win_rate,push_rate,roi_neg110,roi_neg105,"
        "p_value,ci_low,ci_high,insufficient_sample,by_season,profitable_seasons_pct"
    )
    lines = ["# disclaimer", header]
    for r in rows:
        wins = r.get("wins", 50)
        losses = r.get("losses", 40)
        win_rate = wins / (wins + losses)
        lines.append(
            f"{r['bucket']},{r['n']},{wins},{losses},0,"
            f"{win_rate:.6f},0.000000,"
            f"{r['roi']:.6f},{r['roi']:.6f},"
            f"{r['p']:.6f},{r['ci_low']:.6f},{r['ci_high']:.6f},0,"
            f"2020:0.55;2021:0.50;2022:0.60;2023:0.58,"
            f"{r['prof']:.4f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_totals_csv(path: Path, rows: list[dict]) -> None:
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


def _three_csvs(tmp_path):
    ats, totals, ml = tmp_path / "ats.csv", tmp_path / "totals.csv", tmp_path / "ml.csv"
    _write_ats_csv(ats, [
        {"bucket": "ats_lo", "n": 200, "roi": -0.02,
         "ci_low": 0.48, "ci_high": 0.56, "p": 0.40, "prof": 0.4},
        {"bucket": "ats_hi", "n": 300, "roi": 0.06,
         "ci_low": 0.53, "ci_high": 0.61, "p": 0.03, "prof": 0.7},
    ])
    _write_totals_csv(totals, [
        {"bucket": "tot_a", "n": 250, "roi": 0.01,
         "ci_low": 0.50, "ci_high": 0.57, "p": 0.20, "prof": 0.6},
    ])
    _write_ml_csv(ml, [
        {"bucket": "ml_a", "n": 500, "roi": 0.03,
         "ci_low": -0.01, "ci_high": 0.07, "p": 0.10, "prof": 0.6},
    ])
    return ats, totals, ml


def test_no_rows_dropped(tmp_path):
    """Every input bucket appears in the report — nothing is filtered out."""
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    buckets = {r.bucket for r in report}
    assert buckets == {"ats_lo", "ats_hi", "tot_a", "ml_a"}
    assert len(report) == 4


def test_ranked_by_point_roi_desc(tmp_path):
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    rois = [r.point_roi for r in report]
    assert rois == sorted(rois, reverse=True)
    assert report[0].bucket == "ats_hi"   # +0.06, highest
    assert report[-1].bucket == "ats_lo"  # -0.02, lowest


def test_power_columns_populated_and_finite(tmp_path):
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    for r in report:
        assert math.isfinite(r.mde80_roi), f"{r.bucket} mde80_roi not finite"
        assert math.isfinite(r.breakeven_needed_roi), f"{r.bucket} breakeven not finite"
        assert r.mde80_roi > 0
        assert r.breakeven_needed_roi > 0


def test_ml_winrate_blank_ats_populated(tmp_path):
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    by_bucket = {r.bucket: r for r in report}
    assert math.isnan(by_bucket["ml_a"].win_rate)
    assert not math.isnan(by_bucket["ats_hi"].win_rate)


def test_ats_ci_expressed_in_roi(tmp_path):
    """ATS ci_low/ci_high are win-rate Wilson bounds in the source CSV; the report
    must convert them to ROI. ci_low win-rate 0.53 -> roi_from_win_prob(0.53)."""
    from engine.stats_utils import roi_from_win_prob
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    hi = next(r for r in report if r.bucket == "ats_hi")
    assert hi.ci_low == pytest.approx(roi_from_win_prob(0.53), abs=1e-6)
    assert hi.ci_high == pytest.approx(roi_from_win_prob(0.61), abs=1e-6)


def test_missing_csv_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_edge_report(tmp_path / "no_ats.csv", tmp_path / "no_t.csv", tmp_path / "no_ml.csv")


def test_write_edge_report_csv_has_new_schema(tmp_path):
    rows = [
        EdgeRow(
            market="ats", bucket="ats_hi", n=300, win_rate=0.56, point_roi=0.06,
            ci_low=0.011, ci_high=0.165, p_value=0.03, profitable_seasons_pct=0.7,
            mde80_roi=0.12, breakeven_needed_roi=0.08,
        ),
        EdgeRow(
            market="ml", bucket="ml_a", n=500, win_rate=math.nan, point_roi=0.03,
            ci_low=-0.01, ci_high=0.07, p_value=0.10, profitable_seasons_pct=0.6,
            mde80_roi=0.09, breakeven_needed_roi=0.07,
        ),
    ]
    out = tmp_path / "edge_report.csv"
    write_edge_report_csv(rows, out)
    text = out.read_text(encoding="utf-8")
    assert "# Edge report:" in text
    assert "mde80_roi" in text
    assert "# Past performance" in text
    assert (
        "market,bucket,n,win_rate,point_roi,ci_low,ci_high,"
        "p_value,profitable_seasons_pct,mde80_roi,breakeven_needed_roi" in text
    )
    assert "ats,ats_hi,300" in text
    # ML row has a blank win_rate cell (two consecutive commas after n)
    assert "ml,ml_a,500,," in text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_edge_report.py -q`
Expected: FAIL / ImportError — `engine.edge_report` still has the old `credible_edges` API (`rank_credible_edges`, `CredibleEdge`), not `build_edge_report`/`EdgeRow`/`write_edge_report_csv`.

- [ ] **Step 4: Rewrite `engine/edge_report.py`**

Replace the entire contents of `engine/edge_report.py` with:

```python
"""Cross-market edge report.

Reads the three per-market reports (ATS, totals, moneyline-validation), and for
every bucket reports a continuous edge estimate plus the context needed to judge
whether the sample size could confirm a realistic edge. NOT a filter — every
bucket is shown, ranked by point-estimate ROI (descending).

Columns (all ROI-denominated for cross-market comparability):
  - point_roi              : realized ROI (roi_neg110 for ATS/totals, real_roi for ML)
  - ci_low / ci_high       : realized 95% CI, in ROI units
  - p_value                : realized p-value vs breakeven (exact binomial / bootstrap)
  - profitable_seasons_pct : share of seasons profitable
  - mde80_roi              : smallest TRUE edge detectable at this n (80% power, p<0.10)
  - breakeven_needed_roi   : observed edge needed for the CI lower bound to clear breakeven

The two power columns use normal-approximation analytics; the realized CI/p-value
keep their exact/bootstrap methods. For ML, the per-bet PnL std is reconstructed
from the bootstrap CI (see stats_utils.std_from_mean_ci) — a documented approximation.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from tabulate import tabulate

from engine.bucket_analysis import DISCLAIMER
from engine.stats_utils import (
    mde_mean_at_power,
    mde_winrate_at_power,
    mean_needed_for_ci,
    roi_from_win_prob,
    std_from_mean_ci,
    winrate_needed_for_ci,
)


@dataclass(frozen=True)
class EdgeRow:
    market: str
    bucket: str
    n: int
    win_rate: float  # NaN for ML (per-bet odds vary; win rate isn't meaningful)
    point_roi: float
    ci_low: float  # ROI units
    ci_high: float  # ROI units
    p_value: float
    profitable_seasons_pct: float
    mde80_roi: float
    breakeven_needed_roi: float


def _read_csv_skipping_comments(path: Path) -> list[dict]:
    """Read a CSV that may have one or more leading # comment lines."""
    if not path.exists():
        raise FileNotFoundError(f"required CSV not found: {path}")
    with path.open(encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


def _parse_float_or_nan(value: str | None) -> float:
    if value is None or value.strip() == "":
        return math.nan
    return float(value)


def _ats_or_totals_row(market: str, row: dict) -> EdgeRow:
    n = int(row["n"])
    win_rate = _parse_float_or_nan(row["win_rate"])
    point_roi = _parse_float_or_nan(row["roi_neg110"])
    # Source ci_low/ci_high are Wilson bounds on WIN RATE; express in ROI.
    ci_low = roi_from_win_prob(_parse_float_or_nan(row["ci_low"]))
    ci_high = roi_from_win_prob(_parse_float_or_nan(row["ci_high"]))
    mde80_roi = roi_from_win_prob(mde_winrate_at_power(n))
    breakeven_needed_roi = roi_from_win_prob(winrate_needed_for_ci(n))
    return EdgeRow(
        market=market,
        bucket=row["bucket"],
        n=n,
        win_rate=win_rate,
        point_roi=point_roi,
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=_parse_float_or_nan(row["p_value"]),
        profitable_seasons_pct=_parse_float_or_nan(row["profitable_seasons_pct"]),
        mde80_roi=mde80_roi,
        breakeven_needed_roi=breakeven_needed_roi,
    )


def _ml_row(row: dict) -> EdgeRow:
    n = int(row["n"])
    ci_low = _parse_float_or_nan(row["ci_low"])  # already ROI (bootstrap)
    ci_high = _parse_float_or_nan(row["ci_high"])
    # Reconstruct per-bet PnL std from the bootstrap CI (normal-theory approximation).
    std = std_from_mean_ci(ci_low, ci_high, n)
    return EdgeRow(
        market="ml",
        bucket=row["bucket"],
        n=n,
        win_rate=math.nan,
        point_roi=_parse_float_or_nan(row["real_roi"]),
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=_parse_float_or_nan(row["p_value"]),
        profitable_seasons_pct=_parse_float_or_nan(row["profitable_seasons_pct"]),
        mde80_roi=mde_mean_at_power(n, std),
        breakeven_needed_roi=mean_needed_for_ci(n, std),
    )


def build_edge_report(
    ats_path: str | Path,
    totals_path: str | Path,
    ml_path: str | Path,
) -> list[EdgeRow]:
    """Read 3 per-market CSVs, annotate every bucket, rank by point_roi desc.

    No rows are dropped. Buckets with a NaN point_roi sort to the end.
    """
    ats = [_ats_or_totals_row("ats", r) for r in _read_csv_skipping_comments(Path(ats_path))]
    tot = [_ats_or_totals_row("totals", r) for r in _read_csv_skipping_comments(Path(totals_path))]
    ml = [_ml_row(r) for r in _read_csv_skipping_comments(Path(ml_path))]
    rows = ats + tot + ml
    rows.sort(
        key=lambda r: r.point_roi if not math.isnan(r.point_roi) else float("-inf"),
        reverse=True,
    )
    return rows


DEFAULT_ATS_CSV = "data/processed/ats_by_bucket.csv"
DEFAULT_TOTALS_CSV = "data/processed/totals_by_bucket.csv"
DEFAULT_ML_CSV = "data/processed/ml_validation_report.csv"
DEFAULT_OUT_CSV = "data/processed/edge_report.csv"

_REPORT_NOTE = (
    "# Edge report: every bucket shown, ranked by point_roi desc. "
    "Not a buy signal — a measurement."
)
_POWER_NOTE = (
    "# mde80_roi = smallest TRUE edge detectable at this n (80% power, p<0.10). "
    "breakeven_needed_roi = observed edge needed for the CI lower bound to clear "
    "breakeven at this n. Power columns use normal-approximation; realized CI/"
    "p-value use exact-binomial (ATS/totals) or bootstrap (ML)."
)

_HEADER = (
    "market,bucket,n,win_rate,point_roi,ci_low,ci_high,"
    "p_value,profitable_seasons_pct,mde80_roi,breakeven_needed_roi"
)


def _fmt(x: float, prec: int = 6) -> str:
    return "" if isinstance(x, float) and math.isnan(x) else f"{x:.{prec}f}"


def _format_table(rows: list[EdgeRow]) -> str:
    headers = [
        "market", "bucket", "n", "win%", "point_roi",
        "ci_low", "ci_high", "p_value", "prof_seas%", "mde80", "be_needed",
    ]
    out = [
        [
            r.market, r.bucket, r.n,
            _fmt(r.win_rate, 4) or "—",
            f"{r.point_roi:+.4f}" if not math.isnan(r.point_roi) else "—",
            f"{r.ci_low:+.4f}" if not math.isnan(r.ci_low) else "—",
            f"{r.ci_high:+.4f}" if not math.isnan(r.ci_high) else "—",
            _fmt(r.p_value, 4) or "—",
            _fmt(r.profitable_seasons_pct, 4) or "—",
            f"{r.mde80_roi:+.4f}" if not math.isnan(r.mde80_roi) else "—",
            f"{r.breakeven_needed_roi:+.4f}" if not math.isnan(r.breakeven_needed_roi) else "—",
        ]
        for r in rows
    ]
    return tabulate(out, headers=headers, tablefmt="github")


def write_edge_report_csv(rows: list[EdgeRow], path: str | Path) -> None:
    """Write the ranked edge report to CSV with explanatory notes + disclaimer."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_REPORT_NOTE, _POWER_NOTE, f"# {DISCLAIMER}", _HEADER]
    for r in rows:
        lines.append(
            f"{r.market},{r.bucket},{r.n},"
            f"{_fmt(r.win_rate)},{_fmt(r.point_roi)},"
            f"{_fmt(r.ci_low)},{_fmt(r.ci_high)},"
            f"{_fmt(r.p_value)},{_fmt(r.profitable_seasons_pct, 4)},"
            f"{_fmt(r.mde80_roi)},{_fmt(r.breakeven_needed_roi)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _main() -> int:
    """CLI: uv run python -m engine.edge_report"""
    try:
        rows = build_edge_report(DEFAULT_ATS_CSV, DEFAULT_TOTALS_CSV, DEFAULT_ML_CSV)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Hint: run `uv run python -m engine.ats`, `uv run python -m engine.totals`, "
              "and `uv run python -m engine.validation` first.")
        return 1

    print(f"Edge report across all 3 markets ({len(rows)} buckets, ranked by point_roi):\n")
    print(_format_table(rows))
    write_edge_report_csv(rows, DEFAULT_OUT_CSV)
    print(f"\n{DISCLAIMER}")
    print(f"\nCSV written to {DEFAULT_OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
```

- [ ] **Step 5: Run the edge_report tests to verify they pass**

Run: `uv run pytest tests/test_edge_report.py -q`
Expected: PASS (8 tests).

- [ ] **Step 6: Run the full suite + lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all tests pass, ruff clean. (The old `test_credible_edges.py` is gone; `test_edge_report.py` replaces it.)

- [ ] **Step 7: Commit**

```bash
git add engine/edge_report.py tests/test_edge_report.py
git commit -m "feat(edge_report): replace credible-edges filter with honest report

Rename credible_edges -> edge_report. Every bucket is shown, ranked by
point_roi, annotated with mde80_roi (detectable edge at 80% power) and
breakeven_needed_roi. CIs expressed in ROI for cross-market comparison.
ML per-bet std reconstructed from the bootstrap CI.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Docs, cleanup, and pipeline run

**Files:**
- Modify: `README.md` (lines 5, 7, 74-108, 115-116)
- Modify: `scripts/cross_check_ats_totals.py` (line ~10 comment)
- Delete: `data/processed/credible_edges.csv` (if present)
- Update: `.wolf/anatomy.md`, `.wolf/memory.md`, `.wolf/cerebrum.md`

- [ ] **Step 1: Update `scripts/cross_check_ats_totals.py`**

In the docstring/comment around line 10, replace:

```
Decision rule for downstream (engine.credible_edges):
```

with:

```
Decision rule for downstream (engine.edge_report):
```

- [ ] **Step 2: Update `README.md`**

(a) Line 5 — replace the final sentence "Slice 4 adds per-season stability + bootstrap stats for ML and produces a unified cross-market `credible_edges.csv` ranker." with:

```
Slice 4 added per-season stability + bootstrap stats for ML. Slice 5 replaces the binary credible-edges gate with an honest cross-market `edge_report.csv`: every bucket is shown, ranked by point-estimate ROI, annotated with the smallest edge its sample size could detect.
```

(b) Line 7 — append after the Slice 4 reference:

```
 Slice 5 (honest edge report): `2026-05-29-nfl-betting-slice5-design.md` + `2026-05-29-nfl-betting-slice5.md`.
```

(c) Replace the entire "## Slice 4 — Credible-edge ranker" section (lines 74-108) with:

```markdown
## Slice 4 — Credible-edge ranker (superseded by Slice 5)

Slice 4 added Wilson CI / bootstrap CI / p-value / per-season stability across all
three markets and a unified ranker that filtered buckets by four credibility
thresholds. Its headline — "no buckets clear all four thresholds" — was correct but
**overclaimed**: a Slice 5 audit showed the Wilson-lower-bound-beats-breakeven gate
is so conservative it requires roughly +6% to +20% ROI to clear at the available
bucket sizes, while real NFL edges are +1–3% ROI. The "zero survivors" result was
largely the foregone output of an underpowered test, not evidence that no edge exists.

## Slice 5 — Honest edge report

Replaces the binary gate with a measurement. Every bucket is shown, ranked by
point-estimate ROI, with two power columns making detectability explicit.

    # (one-time) verify Kaggle ATS/totals lines match nflverse on the 2020-2024 overlap
    uv run python scripts/cross_check_ats_totals.py

    # refresh per-market reports
    uv run python -m engine.ats
    uv run python -m engine.totals
    uv run python -m engine.validation

    # build the cross-market edge report
    uv run python -m engine.edge_report

Outputs `data/processed/edge_report.csv` with columns:
`market, bucket, n, win_rate, point_roi, ci_low, ci_high, p_value,
profitable_seasons_pct, mde80_roi, breakeven_needed_roi` (all ROI-denominated).

- `mde80_roi` — the smallest **true** edge this bucket's sample size could detect at
  80% power (one-sided, p<0.10). If a bucket's `mde80_roi` exceeds any realistic edge,
  its `n` is too small to ever confirm one.
- `breakeven_needed_roi` — the observed edge the bucket would need for its 95% CI lower
  bound to clear breakeven at its current `n` (the old gate, expressed continuously).

Power columns use a normal approximation; the realized CI/p-value keep their
exact-binomial (ATS/totals) and bootstrap (ML) methods. For ML, the per-bet PnL
standard deviation is reconstructed from the bootstrap CI.

### Honest takeaway

No bucket shows an edge large enough to certify at these sample sizes — but that is a
statement about **power**, not proof of market efficiency. A genuine +2% ROI edge would
be statistically invisible to every bucket here. Any future +EV work needs a
higher-power signal (e.g. closing-line value, which measures price movement per bet
rather than waiting on binary outcomes) rather than finer static partitions.
```

(d) Lines 115-116 — replace the Slice 4 scope bullet and add a Slice 5 bullet:

```
- **Slice 4 (complete):** real-line statistical workup across all 3 markets; unified credible-edge ranker (binary gate; superseded by Slice 5).
- **Slice 5 (complete):** honest edge report — continuous metrics + power/MDE context replacing the binary gate; derived-ML clamp bug fixed.
- **Deferred to later slices:** closing-line-value (CLV) backtest (needs opening-line ingestion — not in current data), per-game-state filters, live odds + this-week pick generator, interactive dashboard.
```

- [ ] **Step 3: Delete the stale output CSV**

```bash
git rm --ignore-unmatch data/processed/credible_edges.csv
```

(If the file was gitignored / never tracked, this is a no-op — that's fine. Also remove an untracked copy if present: in PowerShell, `Remove-Item data/processed/credible_edges.csv -ErrorAction SilentlyContinue`.)

- [ ] **Step 4: Run the full pipeline end-to-end (requires the loaded DB from prior slices)**

Run:
```bash
uv run python -m engine.ats
uv run python -m engine.totals
uv run python -m engine.validation
uv run python -m engine.edge_report
```
Expected: `engine.edge_report` prints a ranked table of all buckets and writes `data/processed/edge_report.csv`. Open the CSV and confirm: every bucket present (no filtering), `mde80_roi` and `breakeven_needed_roi` populated, ML rows have blank `win_rate`.

If `data/db/nfl_betting.sqlite` is absent (fresh checkout), skip this step and note it — the unit tests already cover behavior with synthetic CSVs. Do NOT fabricate the CSV.

- [ ] **Step 5: Update OpenWolf bookkeeping**

- In `.wolf/anatomy.md`: rename the `engine/credible_edges.py` entry to `engine/edge_report.py` (update description to "Cross-market edge report — continuous metrics + power/MDE, no filtering."), and rename the `tests/test_credible_edges.py` entry to `tests/test_edge_report.py`.
- Append a one-line entry to `.wolf/memory.md` summarizing Slice 5.
- Add a Decision Log entry to `.wolf/cerebrum.md`: "Slice 5 replaced the binary credible-edges gate with a continuous edge report + power/MDE columns after an audit found the gate underpowered."

- [ ] **Step 6: Final verification**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all tests pass, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add README.md scripts/cross_check_ats_totals.py .wolf/anatomy.md .wolf/memory.md .wolf/cerebrum.md
git rm --ignore-unmatch data/processed/credible_edges.csv
git commit -m "docs(slice5): honest edge-report framing + cleanup

README reframed (Slice 4 superseded, Slice 5 added), cross_check comment
updated, stale credible_edges.csv removed, wolf bookkeeping updated.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage:**
- Reframe to continuous metrics, no filtering → Task 3 (`build_edge_report` drops nothing, ranks by `point_roi`). ✓
- Power column `mde80_roi` (80% power) → Task 1 `mde_winrate_at_power` / `mde_mean_at_power`, wired in Task 3. ✓
- Power column `breakeven_needed_roi` (observed needed for CI) → Task 1 `winrate_needed_for_ci` / `mean_needed_for_ci`, wired in Task 3. ✓
- "Both columns" decision → both emitted. ✓
- CIs in ROI for cross-market comparability → Task 3 ATS/totals conversion via `roi_from_win_prob`; ML already ROI. ✓
- Rename module + output (Approach A) → Tasks 3 & 4. ✓
- Moneyline clamp bug fix + regression test → Task 2. ✓
- Normal-approx vs exact/bootstrap split stated in output disclaimer → Task 3 `_POWER_NOTE`. ✓
- README + references + stale CSV cleanup → Task 4. ✓
- Out-of-scope items (validation.py, e2e test, bootstrap golden values, 1408/1343, per-game-state, CLV) → untouched. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; every command shows expected output. ✓

**Type consistency:** `EdgeRow` fields are identical in the dataclass (Task 3 Step 4), the test constructor (Task 3 Step 2), and the CSV writer. Function names match between `stats_utils` definitions (Task 1 Step 3), the `edge_report` imports (Task 3 Step 4), and the tests (Task 1 Step 1, Task 3 Step 2): `roi_from_win_prob`, `mde_winrate_at_power`, `winrate_needed_for_ci`, `mde_mean_at_power`, `mean_needed_for_ci`, `std_from_mean_ci`, `build_edge_report`, `write_edge_report_csv`. ✓

**Known approximation (intentional, documented):** ML `std` is reconstructed from the bootstrap CI rather than computed from raw PnL — keeps `validation.py` out of scope per the spec; flagged in code comments and the report's `_POWER_NOTE`.
