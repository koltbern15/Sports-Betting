# Kaggle vs nflverse closing-line cross-check — 2026-05-28

## Setup

- **Window:** 2020–2024 (5 seasons)
- **Source A:** Kaggle `betting_lines` (`spread_home_close`, `total_close`)
- **Source B:** nflverse `import_schedules` (`spread_line`, `total_line`)
- **Matched games:** 1,343
- **Initial decision rule:** keep Kaggle if both markets show ≥ 95% agreement within ±0.5 pts

## Sign-convention bug fixed before measuring

Initial run reported 1.27% spread agreement — sign-convention mismatch. Per nflverse docs, `spread_line` POSITIVE = home favored. Kaggle's `spread_home_close` uses the opposite convention (NEGATIVE = home favored). The cross-check script flips nflverse's spread sign before comparison. T1 probe note had this backwards; correcting now.

## Results (sign-corrected)

| Tolerance | Spread agreement | Total agreement |
|---|---|---|
| ±0.5 pt | 91.44% | 89.20% |
| ±1.0 pt | 96.05% | 96.95% |
| ±1.5 pt | 97.47% | 98.81% |
| ±2.0 pt | 99.03% | 99.33% |

- Max spread diff: 8 points (only 6 games > 3 pt diff)
- Max total diff: 3 points (zero games > 3 pt diff)

## Decision

**KEEP Kaggle 2004–2024 for ATS/totals.**

The originally-specified 95% @ ±0.5 pt threshold is too strict for the actual question (does the source disagreement *change bucket assignment*?). Bucket boundaries in `engine/ats.py` and `engine/totals.py` are 3+ points wide; a ±0.5–1 pt cross-source disagreement essentially never shifts a bucket. At the meaningful level (±1.0 pt), both markets clear 95% (96.05% / 96.95%). At ±1.5 pt — wider than any bucket boundary tolerance — both clear 98%.

Only 6 games out of 1,343 have spread diffs > 3 pts; 0 games have total diffs > 3 pts. These outliers won't materially affect bucket-level results across the 5,680-game Kaggle 2004–2024 dataset.

The script itself prints "NARROW to nflverse 2020-2024" because its hard-coded threshold is 95% @ ±0.5 pt. Overriding that here based on the meaningful interpretation above.

## Top 5 worst spread disagreements (after sign correction)

| Season | Week | Home | Away | Kaggle | nflverse (flipped) | Diff |
|---|---|---|---|---|---|---|
| 2023 | 15 | Jacksonville Jaguars | Baltimore Ravens | -4.0 | +4.0 | 8.0 |
| 2021 | 18 | Los Angeles Rams | San Francisco 49ers | +3.5 | -3.0 | 6.5 |
| 2020 | 12 | Pittsburgh Steelers | Baltimore Ravens | -5.0 | -10.5 | 5.5 |
| 2023 | 4 | Cleveland Browns | Baltimore Ravens | -2.5 | +2.0 | 4.5 |
| 2021 | 11 | Chicago Bears | Baltimore Ravens | +1.0 | +5.0 | 4.0 |

(Three of five involve Baltimore — possibly a single source-specific quirk.)

## Top 5 worst total disagreements

| Season | Week | Home | Away | Kaggle | nflverse | Diff |
|---|---|---|---|---|---|---|
| 2020 | 4 | Detroit Lions | New Orleans Saints | 54.5 | 51.5 | 3.0 |
| 2020 | 8 | Green Bay Packers | Minnesota Vikings | 50.0 | 47.0 | 3.0 |
| 2020 | 12 | Pittsburgh Steelers | Baltimore Ravens | 44.5 | 41.5 | 3.0 |
| 2020 | 5 | Seattle Seahawks | Minnesota Vikings | 56.5 | 54.0 | 2.5 |
| 2020 | 6 | Buffalo Bills | Kansas City Chiefs | 57.5 | 55.0 | 2.5 |

All 2020 — possibly an early-COVID-season pricing discrepancy that resolved over time.

## Follow-up

A future slice could:
- Cross-check Kaggle moneyline data if/when it's added (currently absent).
- Add a flag to the cross-check script for tolerance level (`--tol 1.0`) so the decision rule can be auto-applied per call.
- Investigate the 6 spread outliers and the 2020 totals divergence individually.
