# NFL Betting Analytics — Slice 4: Real-Line Statistical Workup + Credible Edges Ranker

**Date:** 2026-05-27
**Status:** Approved (brainstorming complete)
**Predecessor:** Slice 3 (`docs/superpowers/specs/2026-05-27-nfl-betting-slice3-design.md`)
**Implementation plan:** `docs/superpowers/plans/2026-05-27-nfl-betting-slice4.md` (to be written)

---

## Goal

Apply real-line statistical rigor across all three markets (ATS, totals, moneyline) and produce a unified ranked report — `credible_edges.csv` — listing the buckets that meet a credibility threshold.

Slice 3 surfaced one candidate real-line edge (`ml_small_fav` at +1.03% real ROI on n=562) but didn't statistically characterize it (no Wilson CI on the real ROI, no p-value vs breakeven, no season-by-season stability). Slice 4 fills that gap and extends the same treatment to ATS and totals. The deliverable is a single CSV that filters across all three markets to the buckets meeting four credibility conditions and ranks them by the most conservative true-edge estimate (Wilson 95% CI lower bound).

## Out of scope (deferred)

- Live odds + this-week pick generator (Slice 5 candidate)
- Static HTML report or Streamlit dashboard (Slice 6 candidate)
- Backtest framework — equity curve, drawdown, CLV (Slice 7 candidate)
- Per-game-state partitioning (home/road, divisional, primetime) within buckets
- Extending real-line ML coverage pre-2020

---

## Time-window decision

- **ATS + Totals:** 2004–2024 from Kaggle (5,680 games). One-time cross-check against nflverse 2020–2024 confirms Kaggle's closing spreads/totals match real lines; if confirmed, full 21-year window stays.
- **Moneyline:** 2020–2024 from nflverse (1,343 matched games from Slice 3). Real prices only — Slice 3 proved derived prices are biased.

If the cross-check fails (spread or total agreement < 95%), narrow ATS/totals to 2020–2024 nflverse and re-run. The plan must include both paths.

---

## Architecture

**Additive — no restructuring of existing engine modules.** `engine/ats.py`, `engine/totals.py`, `engine/moneyline.py`, `engine/validation.py` keep their current shapes. New behavior layered on top.

**Three changes:**

1. **One new shared metric** — `profitable_seasons_pct` — added to `BucketMetrics` in `engine/bucket_analysis.py`. All three per-market CSVs (ATS, totals, ML-derived) pick it up automatically.
2. **`compare_ml_prices` extended** to compute per-season real_roi and produce `profitable_seasons_pct` for ML buckets, since the Slice 3 ValidationReport doesn't currently carry it.
3. **One new module** — `engine/credible_edges.py` — reads the three per-market CSVs, normalizes to a common shape, filters by the four credibility thresholds, ranks survivors by Wilson lower bound, writes `data/processed/credible_edges.csv`.

**One cross-check script** — `scripts/cross_check_ats_totals.py` — runs once, prints/writes Kaggle-vs-nflverse spread/total agreement findings. Outcome drives the time-window decision above.

**No schema changes. No new dependencies.**

---

## Components

| File | Responsibility | Lifecycle in Slice 4 |
|---|---|---|
| `engine/bucket_analysis.py` | Add `profitable_seasons_pct` field + computation in `compute_metrics` | MODIFY |
| `tests/test_bucket_analysis.py` | Tests for new metric | MODIFY |
| `engine/validation.py` | Extend `compare_ml_prices` + `ValidationReport` to include per-bucket profitable_seasons_pct | MODIFY |
| `tests/test_validation.py` | Tests for per-season ROI + profitable_seasons_pct on ML buckets | MODIFY |
| `scripts/cross_check_ats_totals.py` | One-time Kaggle-vs-nflverse spread/total cross-check | NEW |
| `docs/superpowers/notes/2026-05-28-kaggle-nflverse-crosscheck.md` | Cross-check outcome record | NEW |
| `engine/credible_edges.py` | Cross-market ranker + CLI | NEW |
| `tests/test_credible_edges.py` | Tests with synthetic per-market CSVs | NEW |
| `README.md` | Slice 4 section + headline finding | MODIFY |

---

## Credibility thresholds

A bucket must satisfy ALL four:

| Condition | Value | Rationale |
|---|---|---|
| `n ≥ 100` | 100 bets minimum | Statistical-power floor; smaller samples are dominated by noise. |
| `wilson_ci_lower > 0` | 95% lower bound positive | "95% confident the true edge is positive" — most conservative pass criterion. |
| `p_value < 0.10` | Modest evidence vs breakeven | Not strict-significance (0.05), but rules out flat results. |
| `profitable_seasons_pct ≥ 0.60` | Stable across time | Rules out buckets where one freak season carries the result. |

Survivors are **ranked by `wilson_ci_lower` descending** — the most conservative estimate of true edge.

Thresholds are starting values; tune-able via CLI flags in a future slice if needed.

---

## End-to-end workflow

Assumes Slices 1–3 outputs exist (Kaggle loaded, nflverse real-ML loaded).

```
1. uv run python scripts/cross_check_ats_totals.py
   → prints agreement %, writes findings doc
   → decides time-window for ATS/totals (no automated fork in this slice; user reads finding and chooses)

2. uv run python -m engine.ats         # re-runs with new profitable_seasons_pct column
3. uv run python -m engine.totals      # ditto
4. uv run python -m engine.validation  # ditto (ML report also gets per-bucket profitable_seasons_pct)

5. uv run python -m engine.credible_edges
   → tabulated stdout + data/processed/credible_edges.csv
```

---

## profitable_seasons_pct semantics

Each `BucketMetrics` already carries `by_season: dict[int, float]` (per-season win-rate). New field:

```
profitable_seasons_pct: float
```

- For ATS/totals: `profitable = (per-season win_rate > 0.5238)` (-110 breakeven).
- For ML: bucket-average odds vary, so win_rate threshold doesn't apply. Use `profitable = (per-season real_roi > 0)`. Requires extending `compare_ml_prices` to group bucket_rows by season and compute per-season real ROI.
- Returns `NaN` if `by_season` has < 3 seasons (not enough to assess stability). Filter treats NaN as failing the 0.60 threshold.

---

## credible_edges.py output

CSV columns (one row per surviving bucket, sorted by wilson_ci_lower desc):

```
market,bucket,n,roi,ci_low,ci_high,p_value,profitable_seasons_pct
```

Header comment lines:

```
# Credible-edge thresholds: n>=100, ci_low>0, p<0.10, profitable_seasons>=0.60. Ranked by ci_low desc.
# Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.
```

For ML rows, `roi` is `real_roi` (not derived — Slice 3 showed derived is biased).

Stdout: same data via `tabulate` + disclaimer. If no buckets survive: empty CSV (header only) + explicit stdout message "No buckets meet credibility thresholds."

---

## Error handling

- `credible_edges.py` missing any input CSV → print "Run `python -m engine.{ats|totals|validation}` first", exit 1.
- `cross_check_ats_totals.py` if nflverse fetch fails → print error, exit 1. Sanity-check tool, not pipeline-critical.
- `profitable_seasons_pct` with 0 seasons → NaN (handled by filter).
- All file I/O uses `pathlib` + `utf-8`.

---

## Testing

- **`tests/test_bucket_analysis.py`** — ~3 new tests:
  - all seasons profitable → 1.0
  - no seasons profitable → 0.0
  - < 3 seasons → NaN
- **`tests/test_validation.py`** — ~2 new tests:
  - per-season real_roi computed correctly from bucket_rows grouped by season
  - profitable_seasons_pct = share of seasons with real_roi > 0
- **`tests/test_credible_edges.py`** — ~6 new tests using synthetic per-market CSVs in `tmp_path`:
  - happy path: filter + rank produces expected ordering
  - n < 100 rejected
  - ci_low ≤ 0 rejected
  - p_value ≥ 0.10 rejected
  - profitable_seasons_pct < 0.60 rejected
  - empty input (no surviving buckets) → header-only CSV + helpful stdout

No tests for the cross-check script (one-off exploratory tool; the notes doc is the deliverable).

Target: ~233 total tests passing (222 baseline + ~11 new).

---

## Definition of Done

- [ ] `BucketMetrics.profitable_seasons_pct` field exists; `compute_metrics` computes it
- [ ] Re-running `engine.ats`, `engine.totals` produces CSVs that include the new column
- [ ] `compare_ml_prices` extended to compute per-season real_roi → ML buckets carry `profitable_seasons_pct`
- [ ] `scripts/cross_check_ats_totals.py` runs against real data, writes findings doc
- [ ] Time-window decision recorded in findings doc (ATS/totals stay on Kaggle 2004–2024 OR narrow to 2020–2024 nflverse)
- [ ] `engine/credible_edges.py` + CLI exists; produces `data/processed/credible_edges.csv`
- [ ] `tests/test_credible_edges.py` ≥ 6 passing tests
- [ ] `uv run pytest -q` ~233 tests passing
- [ ] `uv run ruff check .` clean
- [ ] Full pipeline runs end-to-end producing a non-empty (or explicitly empty) credible_edges output
- [ ] README updated with Slice 4 section + headline finding (which buckets cleared the four thresholds, ranked)
- [ ] `.wolf/memory.md` finding entry
- [ ] Tag `slice4-complete`

---

## Decisions log (this slice)

- **Time window:** 2004–2024 Kaggle for ATS/totals (gated on cross-check pass), 2020–2024 nflverse for ML. Maximizes statistical power per market without trusting derived ML.
- **Output shape:** three enriched per-market reports + ONE ranked `credible_edges.csv`. Per-market detail preserved; cross-market actionable summary added.
- **Credibility thresholds:** n≥100, Wilson ci_low > 0, p<0.10, profitable_seasons ≥ 60%. Rank by ci_low desc (most conservative true-edge estimate).
- **Architecture:** additive over existing engine modules; new metric in shared `bucket_analysis.py`, new ranker reads CSVs (loose integration surface, easy to refactor later).
- **For ML buckets:** ranker uses `real_roi` from Slice 3, not `derived_roi`. Slice 3 showed derived is biased.
- **Cross-check is one-off script + notes doc**, not a proper module. Outcome drives the time-window decision; if the answer is stable, no need to keep running it.
