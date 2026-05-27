# NFL Betting Analytics — Slice 2 Design

**Date:** 2026-05-27
**Status:** Approved for planning
**Prior slice:** [Slice 1 design](2026-05-26-nfl-betting-slice1-design.md) — ATS-by-spread-bucket analysis, complete.

## Goal

Extend the historical-edge analysis from one market (against-the-spread) to three (ATS, totals, moneyline), reusing Slice 1's loader, schema, and statistical machinery. After Slice 2 the project answers three historical questions with full statistical rigor:

1. Which spread ranges (if any) beat the book against the spread? *(Slice 1)*
2. Which total-line ranges beat over or under?
3. Which moneyline-price ranges beat the implied win probability?

The output of Slice 2 is the historical-edge map that future slices (live odds, best-bets engine, dashboard) will consume.

## Non-goals

- Live or near-real-time odds. Deferred to Slice 3.
- A best-bets recommendation engine. Deferred to Slice 3.
- Any UI / dashboard. Deferred to Slice 4.
- Splits by primetime / divisional / weather / dome. Possible separate "depth" slice.
- Predictive modeling (logistic regression, ML classifier). Out of scope.
- Composite or parlay analysis. Out of scope.
- Schema migrations. Slice 2 reads from the Slice 1 schema unchanged.

## Architecture

### Module layout after Slice 2

```
engine/
  stats_utils.py          # existing + 1 new function (dollar_weighted_roi)
  bucket_analysis.py      # NEW — shared dataclass + helpers (refactored out of ats.py)
  ats.py                  # slimmed: bucket_spread, ats_by_spread_bucket, CLI
  totals.py               # NEW — bucket_total, totals_by_line_bucket, CLI
  moneyline.py            # NEW — derive_ml_from_spread, bucket_ml, moneyline_by_odds_bucket, CLI
  db.py                   # unchanged
ingestion/                # unchanged
```

### Shared bucket-analysis module

`engine/bucket_analysis.py` is extracted from `engine/ats.py` as Task 1 of Slice 2. It owns:

- `BucketMetrics` dataclass (n, wins, losses, pushes, win_rate, push_rate, roi_neg110, roi_neg105, p_value, ci_low, ci_high, insufficient_sample, by_season)
- `INSUFFICIENT_SAMPLE_THRESHOLD = 30`
- `compute_metrics(wins, losses, pushes, *, payouts=None) -> BucketMetrics`
   - Default behavior unchanged from Slice 1 (computes ROI at fixed -110/-105 from win counts).
   - When `payouts` is supplied (list of per-bet net unit profits), it overrides the ROI calculations with `dollar_weighted_roi(payouts)`. The fixed-vig ROI columns are still emitted but flagged `n/a` in the table.
- `format_table(report: dict[str, BucketMetrics], *, bucket_order: list[str]) -> str` — tabulate output, identical look across all 3 modules.
- `write_csv(report: dict[str, BucketMetrics], path: Path, *, bucket_order: list[str]) -> None`
- `DISCLAIMER = "Past performance does not guarantee future results. ..."`

After this refactor, `engine/ats.py` keeps only its bucket-classification function (`bucket_spread`), its aggregator (`ats_by_spread_bucket`), and its CLI entry. All three module CLIs (`ats`, `totals`, `moneyline`) call `bucket_analysis.format_table` and `bucket_analysis.write_csv` so the user sees a consistent format across markets.

### Totals module

`engine/totals.py` adds:

- `bucket_total(total_line: float | None) -> str | None`
  - 6 buckets, boundaries inclusive on the lower end except the open lowest: `total_le_39_5`, `total_40_42_5`, `total_43_45_5`, `total_46_48_5`, `total_49_51_5`, `total_ge_52`.
  - Returns `None` if `total_line is None`.
- `totals_by_line_bucket(conn: sqlite3.Connection) -> dict[str, BucketMetrics]`
  - SQL: `SELECT season, total_line, total_result FROM games JOIN betting_lines USING (game_id) WHERE total_result IS NOT NULL`.
  - Group by `bucket_total(total_line)`.
  - Count outcomes from `total_result` (`over` → win, `under` → loss, `push` → push).
  - Call `bucket_analysis.compute_metrics(wins, losses, pushes)` per bucket.
  - Compute by-season trend per bucket where bucket has n ≥ 30 in the season.
- CLI entry: `python -m engine.totals` → prints table + writes `data/processed/totals_by_bucket.csv`.

Bucket order convention (low → high) is preserved in the table.

### Moneyline module

`engine/moneyline.py` adds:

- `derive_ml_from_spread(spread_home_close: float | None) -> tuple[int, int] | None`
  - Pure function. Returns `(ml_home, ml_away)` as integer American odds.
  - Math: `P_home_novig = 0.5 * (1 + erf(-spread_home_close / (σ * sqrt(2))))` with `σ = 13.86`.
  - Apply proportional vig with target overround `1.04762` (matches standard -110/-110 = 2.10 decimal payout structure).
  - Convert each vigged probability to American odds via standard formula.
  - Returns `None` if input is `None`.
  - Hand-verified reference values used in tests:

    | spread_home | P_home no-vig | ML_home | ML_away |
    |---|---|---|---|
    |  0.0 | 0.500 | -110 | -110 |
    | -3.0 | 0.586 | -159 | +130 |
    | -7.0 | 0.693 | -265 | +211 |
    | -14.0 | 0.844 | -762 | +511 |
    | +3.0 | 0.414 | +130 | -159 |

  - Tolerance: ±2 on American odds (rounding boundary cases).
  - Values above computed with `OVERROUND = 1.04762`, `SIGMA = 13.86`, banker's-style rounding of the American conversion.

- `bucket_ml(ml_price: int | None) -> str | None`
  - 11 buckets mirroring the ATS structure:

    | bucket | boundary |
    |---|---|
    | `ml_heavy_fav`  | ml ≤ -300 |
    | `ml_big_fav`    | -300 < ml ≤ -250 |
    | `ml_mid_fav`    | -250 < ml ≤ -180 |
    | `ml_small_fav`  | -180 < ml ≤ -130 |
    | `ml_slight_fav` | -130 < ml ≤ -110 |
    | `ml_pickem`     | -110 < ml < +110 |
    | `ml_slight_dog` | +110 ≤ ml < +130 |
    | `ml_small_dog`  | +130 ≤ ml < +180 |
    | `ml_mid_dog`    | +180 ≤ ml < +250 |
    | `ml_big_dog`    | +250 ≤ ml < +300 |
    | `ml_heavy_dog`  | ml ≥ +300 |

- `moneyline_by_odds_bucket(conn: sqlite3.Connection) -> dict[str, BucketMetrics]`
  - SQL: `SELECT season, spread_home_close, score_home, score_away FROM games JOIN betting_lines USING (game_id) WHERE spread_home_close IS NOT NULL AND score_home IS NOT NULL`.
  - For each row, derive `(ml_home, ml_away)` from spread; emit **two perspectives per game** — one row for the home side, one for the away side — bucketed by that side's ML price.
  - Outcome: win if that side won outright, loss if not, push if tied (NFL ties are rare, ~5 in 5,680 games).
  - Payout per bet: `+ml/100` if favorite wins on positive American, or `+100/|ml|` for negative American; `-1` for loss; `0` for push.
  - Call `bucket_analysis.compute_metrics(wins, losses, pushes, payouts=payouts)` per bucket so ROI uses variable per-bet payouts.
- CLI entry: `python -m engine.moneyline` → prints table prefixed with `"NOTE: Moneyline prices derived from closing spreads via normal-CDF + vig — NOT real historical sportsbook ML."` + writes `data/processed/moneyline_by_bucket.csv` with the same note in row 1.

### stats_utils extension

Add one pure function:

```python
def dollar_weighted_roi(payouts: list[float]) -> float:
    """ROI per unit stake given a list of per-bet net profits.
    Returns 0.0 if payouts is empty. Each payout: +N for win at price implying N units profit,
    -1.0 for loss, 0.0 for push."""
    return sum(payouts) / len(payouts) if payouts else 0.0
```

Three tests: all-wins-at-fixed-price, all-losses, mixed.

## Data flow

Identical for totals and moneyline:

```
SQLite (games + betting_lines, from Slice 1)
        │
        ▼
SELECT … FROM games JOIN betting_lines  (no schema change)
        │
        ▼
For each row → bucket_*() classification + outcome derivation
        │
        ▼
Group by bucket → (wins, losses, pushes[, payouts])
        │
        ▼
bucket_analysis.compute_metrics() per bucket
        │
        ▼
format_table() to stdout + write_csv() to data/processed/
```

## Testing strategy

| Test file | Coverage |
|---|---|
| `tests/test_stats_utils.py` (extend) | `dollar_weighted_roi` (3 cases) |
| `tests/test_bucket_analysis.py` (new) | smoke tests for refactored helpers (`format_table`, `write_csv`); verify ATS module still produces identical output post-refactor |
| `tests/test_totals.py` (new) | `bucket_total` (8 parametrized cases incl. None and boundary values); `totals_by_line_bucket` against `tests/fixtures/totals_20.csv` |
| `tests/test_moneyline.py` (new) | `derive_ml_from_spread` (5 reference values + None); `bucket_ml` (12 parametrized cases incl. boundary values); `moneyline_by_odds_bucket` against `tests/fixtures/moneyline_20.csv` |
| `tests/test_ats.py` (existing) | Must remain green after T1 refactor without modification beyond import path updates |

### Hand-verified fixture discipline

Each integration fixture (`totals_20.csv`, `moneyline_20.csv`) is hand-built with a comment in the test file mapping each game row to its expected bucket. Per-bucket expected counts are asserted explicitly (e.g., `assert metrics["total_46_48_5"].n == 4 and metrics["total_46_48_5"].wins == 3 and metrics["total_46_48_5"].losses == 1`). This is the same discipline used for `games_20_ats.csv` in Slice 1.

Target: ~40–50 new tests across the slice. All existing 119 Slice 1 tests must remain green.

## CLI contract

| Command | Output to stdout | Output to disk |
|---|---|---|
| `python -m engine.ats` | tabulated table + disclaimer | `data/processed/ats_by_bucket.csv` |
| `python -m engine.totals` | tabulated table + disclaimer | `data/processed/totals_by_bucket.csv` |
| `python -m engine.moneyline` | derivation note + tabulated table + disclaimer | `data/processed/moneyline_by_bucket.csv` (with note as row 1) |

All three accept default DB path `data/db/nfl_betting.sqlite`. No CLI flags planned for Slice 2.

## Definition of Done

- [ ] `engine/bucket_analysis.py` exists with the shared dataclass + helpers; `engine/ats.py` imports and reuses them.
- [ ] `engine/totals.py` and `engine/moneyline.py` exist with their bucket fn, aggregator, and CLI.
- [ ] `engine/stats_utils.dollar_weighted_roi` exists with tests.
- [ ] All 119 prior tests pass.
- [ ] ~40–50 new tests pass.
- [ ] `uv run ruff check .` clean.
- [ ] Both new CLIs run against the real 5,680-game DB and produce plausible tables.
- [ ] `data/processed/totals_by_bucket.csv` and `data/processed/moneyline_by_bucket.csv` written.
- [ ] README updated with the 2 new commands and the moneyline-derivation caveat.
- [ ] Tag `slice2-complete` cut.

## Risks and caveats

- **Synthetic ML prices.** The moneyline analysis uses spread-derived prices, not real historical sportsbook ML. Findings will reflect the *spread market's* efficiency expressed in ML form, not the *ML market's* independent efficiency. This must be surfaced in CLI output, CSV, and README. Slice 3 (live odds) will analyze real ML prices going forward.
- **σ choice.** `NFL_MARGIN_SIGMA = 13.86` is the Burke / AdvancedNFL consensus value for the post-2000 era. If the value is materially wrong, derived ML prices will be biased — but since the analysis is bucketed by *derived* price, the buckets will still self-consistently slice the data. Worth a sanity check against a small sample of known historical ML prices if a free source surfaces.
- **NFL ties.** ~5 ties in 5,680 games (≤0.1%). Treated as moneyline push. Statistically immaterial.
- **Sample size in tail buckets.** `ml_heavy_fav` and `ml_heavy_dog` will have small n (likely < 50). Wilson CI handles this; small-sample buckets are flagged `*` per Slice 1's convention.

## Open questions

None blocking. Possible future tuning (not in scope for Slice 2):

- Bucket boundaries can be adjusted post-hoc if the natural distribution of historical data makes one bucket too small or too large.
- The variable-payout ROI for ML could optionally also compute a "fair-price ROI" (no-vig) for comparison. Punted unless useful in practice.
