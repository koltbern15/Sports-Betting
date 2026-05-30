# NFL Betting Analytics — Slice 5: Honest Edge Report (continuous metrics + power context)

**Date:** 2026-05-29
**Status:** Approved (brainstorming complete)
**Predecessor:** Slice 4 (`docs/superpowers/specs/2026-05-27-nfl-betting-slice4-design.md`)
**Implementation plan:** `docs/superpowers/plans/2026-05-29-nfl-betting-slice5.md` (to be written)

---

## Why this slice

A four-agent audit (stats methodology / code correctness / data quality / tests + roadmap) found that Slice 4's headline — "ZERO buckets clear all four credibility thresholds, so static bucket strategies don't survive scrutiny" — is **statistically true but overclaimed**.

The binding constraint, "Wilson CI *lower bound* must beat breakeven," is so conservative that clearing it requires roughly:

| Bucket size | Observed ROI needed to "pass" |
|---|---|
| n = 100 | ~ +20% |
| n = 500 | ~ +8% |
| n = 1,000 | ~ +6% |
| n = 5,680 (full pool) | ~ +2.5% |

Real, exploitable NFL edges are **+1–3% ROI**, and no single bucket is large enough for a genuine 2% edge to clear the bar. So "zero survivors" is largely the foregone output of an **underpowered** test — not independent evidence that no edge exists. The binary gate hides this: a bucket with a real-but-small estimated edge and a bucket that is genuinely flat both render identically as "filtered out."

This slice replaces the verdict with a **measurement**: every bucket is shown with its estimated edge, its uncertainty, and the context needed to judge whether the sample size could ever confirm a realistic edge.

## Goal

Turn the cross-market ranker from a *filter* into an *edge report*. Show every bucket (no rows dropped), ranked by point-estimate edge, annotated with two power columns that make detectability explicit. Also fix a silent-wrong-value bug in the derived-moneyline price math surfaced by the audit.

## Out of scope (deferred)

- End-to-end producer→report pipeline contract test (audit gap; later hardening slice)
- Bootstrap golden-value tests (audit gap; later hardening slice)
- Reconciling the 1,408 → 1,343 nflverse/Kaggle game gap (audit finding; later)
- Per-game-state partitioning (audit warns it worsens the power problem)
- CLV / opening-line ingestion (blocked: no opening lines in schema, nflverse doesn't supply them)
- Dashboard, live odds, this-week pick generator

---

## Architecture (Approach A — repurpose in place, rename the deliverable)

**Additive + one rename. No schema changes, no new dependencies.**

The existing `engine/credible_edges.py` already reads the three per-market CSVs (ATS, totals, ML), normalizes them to a common shape, **filters** by four gates, and ranks survivors. Approach A keeps the normalization, replaces the filter step with a measure-and-annotate step, and renames the module/output because the name "credible_edges" *is* the verdict framing being abandoned.

| File | Responsibility | Lifecycle in Slice 5 |
|---|---|---|
| `engine/credible_edges.py` → `engine/edge_report.py` | Rename module. Replace filter-and-drop with measure-and-annotate: keep every bucket, add power columns, rank by point estimate. Reuse existing CSV normalization. | RENAME + MODIFY |
| `engine/stats_utils.py` | Add two pure helpers: `mde_at_power` and `obs_needed_for_ci` (see Math). | MODIFY |
| `engine/moneyline.py` | Fix derived-price clamp bug in `derive_ml_from_spread` / `_prob_to_american`. | MODIFY |
| `tests/test_credible_edges.py` → `tests/test_edge_report.py` | Rename. Rewrite assertions: no rows dropped, ranking correct, new columns populated and sane. | RENAME + MODIFY |
| `tests/test_stats_utils.py` | Hand-verified golden-value tests for the two new helpers. | MODIFY |
| `tests/test_moneyline.py` | Regression test: steep-spread game yields a sane price (≥ −10000), not −99,999,900. | MODIFY |
| `data/processed/credible_edges.csv` → `data/processed/edge_report.csv` | Output rename. | RENAME |
| `README.md` | Replace the "zero credible edges" framing with the honest edge-report framing + the underpowered-test finding. | MODIFY |

---

## Scope honesty note (the clamp bug and the report)

The clamp bug lives in `engine/moneyline.py`, which produces **derived** ML prices. The edge report's ML rows come from **real** nflverse prices via `engine/validation.py` (`compare_ml_prices`), so the report's ML numbers are **not** distorted by the clamp.

The bug is fixed anyway because (a) the derived-ML report (`moneyline_by_bucket.csv`) is still published and still feeds the "derived prices are biased" comparison from Slices 2–3, and (b) it is a genuine silent-wrong-value bug in active code. This is recorded explicitly so the spec does not overstate the bug's reach.

---

## The new math (two helpers in `stats_utils.py`)

For each bucket we already compute the realized estimate, CI, and p-value — exact binomial + Wilson for ATS/totals, bootstrap for ML. These are **unchanged**. We add two analytic columns.

Both new helpers use **normal-approximation analytics** (one-sided, α = 0.10, power = 0.80, z_α = `norm.ppf(0.90)`, z_β = `norm.ppf(0.80)`). The realized CI/p-value keep their exact/bootstrap methods. This split is intentional and will be stated in code comments and the report disclaimer so it is not read as an inconsistency.

### `mde_at_power(n, ...) -> float`  — minimum detectable edge at 80% power

"The smallest *true* edge this bucket's sample size could reliably detect."

- **ATS / totals (binomial vs null p0 = 0.5238):** solve numerically for the smallest true win rate `p1 > p0` satisfying the one-sample-proportion power equation
  `n = (z_α·√(p0(1−p0)) + z_β·√(p1(1−p1)))² / (p1 − p0)²`.
  Solve for `p1` by bisection on `(p0, 1)` (no closed form). Return as **ROI** via `roi(p1) = p1·(1 + 100/110) − 1`.
- **ML (mean PnL vs null 0):** `mde_mean = (z_α + z_β)·s/√n`, where `s` is the per-bet PnL standard deviation. Already in ROI units.

### `obs_needed_for_ci(n, ...) -> float`  — observed edge needed to clear breakeven CI

"The observed win%/ROI this bucket would need for its CI lower bound to beat breakeven at its current n." (The audit-agent framing; ties back to the old gate.)

- **ATS / totals:** smallest observed win count `w` such that `wilson_ci(w, n)` lower bound > 0.5238 (search `w`; Wilson lower bound is monotonic in `w`). Return as ROI.
- **ML:** smallest observed mean such that `mean − z_α·s/√n > 0`, i.e. `mean > z_α·s/√n`. Already in ROI units.

Both return `NaN` for `n = 0` (handled by the report writer).

---

## `edge_report.py` output

One row per bucket, **all** buckets across all three markets, **sorted by `point_roi` descending** (best apparent edge first — no rows dropped). Values in ROI % where possible for cross-market comparability.

CSV columns:

```
market,bucket,n,win_rate,point_roi,ci_low,ci_high,p_value,profitable_seasons_pct,mde80_roi,breakeven_needed_roi
```

- `win_rate` — blank for ML rows (odds vary per bet; win rate isn't meaningful). Populated for ATS/totals.
- `point_roi` — `roi_neg110` for ATS/totals, `real_roi` for ML.
- `ci_low` / `ci_high` — the realized 95% CI, expressed in **ROI** for all markets (ATS/totals win-rate bounds converted to ROI at −110) so the column is comparable across markets.
- `mde80_roi` — output of `mde_at_power`.
- `breakeven_needed_roi` — output of `obs_needed_for_ci`.
- No categorical pass/fail label (design choice: continuous + power context, not soft tiers).

Header comment lines (replace the old threshold note):

```
# Edge report: every bucket shown, ranked by point_roi desc. Not a buy signal — a measurement.
# mde80_roi = smallest TRUE edge detectable at this n (80% power, p<0.10). breakeven_needed_roi = observed edge needed for CI lower bound to clear breakeven at this n.
# Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.
```

Stdout: same data via `tabulate` + disclaimer. The report is never empty (no filtering); if an input CSV has zero buckets, that market simply contributes no rows.

---

## The bug fix (`engine/moneyline.py`)

At home spreads steeper than ~−24, `p_home_nv · 1.04762` (overround) exceeds 1.0; the current `1e-6` clamp pins the vigged probability at `1 − 1e-6`, and `_prob_to_american` returns **−99,999,900**. Bucketing is unaffected (anything ≤ −300 → `ml_heavy_fav`), but a winning heavy-favorite payout becomes `100/99,999,900 ≈ 0.000001` instead of a realistic ~0.005, silently understating `ml_heavy_fav` ROI in the derived report.

**Fix:** cap the vigged implied probability so the derived American price floors at a sane value (≈ −10000, implied ~0.9901) rather than −99,999,900. Implement as a named constant with an inline comment explaining the cap and why proportional vig produces >1 probabilities at extreme favorites. The exact constant is finalized in the implementation plan; design intent is "sane floor near −10000, realistic heavy-fav payout."

---

## Error handling

- `edge_report.py` missing any input CSV → print "Run `python -m engine.{ats|totals|validation}` first", exit 1 (unchanged behavior).
- `mde_at_power` / `obs_needed_for_ci` with `n = 0` → `NaN`; writer emits blank cell.
- Bisection in `mde_at_power` is bounded to `(p0, 1)` with a fixed iteration cap; if it fails to converge it returns `NaN` (treated as "not computable") rather than raising.
- All file I/O uses `pathlib` + `utf-8`.

---

## Testing

- **`tests/test_stats_utils.py`** — golden-value tests (real reference values, matching the suite's existing standard):
  - `mde_at_power` for ATS/totals at n = 100 / 500 / 1000 matches the audit's win-rate figures (~63% / ~56.8% / ~55.5%) within tolerance, converted to ROI.
  - `mde_at_power` for ML matches the closed-form `(z_α+z_β)·s/√n` for a known `s`, `n`.
  - `obs_needed_for_ci` (ATS/totals) returns a win count whose Wilson lower bound is just above 0.5238 and where one fewer win is just below.
  - `obs_needed_for_ci` (ML) matches `z_α·s/√n`.
  - `n = 0` → `NaN` for both.
- **`tests/test_edge_report.py`** (renamed):
  - no rows dropped — every input bucket appears in output.
  - rows sorted by `point_roi` descending.
  - `mde80_roi` and `breakeven_needed_roi` populated and within sane bounds (positive, finite for n>0).
  - ML rows have blank `win_rate`; ATS/totals rows populated.
  - CI columns expressed in ROI (ATS/totals bounds converted, not raw win-rate).
- **`tests/test_moneyline.py`** — regression: a game at spread −26.5 produces a derived favorite price ≥ −10000 (not −99,999,900), and the resulting heavy-fav payout is realistic (> 0.001).
- Full suite stays green and ruff clean.

Target: ~245 baseline minus retired filter-only tests plus new ones — net roughly flat to slightly up; exact count finalized in the plan.

---

## Definition of Done

- [ ] `engine/credible_edges.py` renamed to `engine/edge_report.py`; filter replaced with measure-and-annotate; no rows dropped; ranked by `point_roi` desc
- [ ] `stats_utils.mde_at_power` + `stats_utils.obs_needed_for_ci` exist, pure, golden-value tested
- [ ] `data/processed/edge_report.csv` produced with the new columns + updated disclaimer
- [ ] `engine/moneyline.py` clamp bug fixed; derived steep-spread price floors near −10000; regression test passing
- [ ] `tests/test_edge_report.py` (renamed) asserts no-drop + ranking + populated power columns
- [ ] `README.md` updated: honest edge-report framing replaces "zero credible edges"; underpowered-test finding stated
- [ ] `uv run pytest -q` green; `uv run ruff check .` clean
- [ ] Pipeline runs end-to-end producing a populated `edge_report.csv`
- [ ] `.wolf/memory.md` finding entry; `.wolf/cerebrum.md` decision-log entry
- [ ] Old `data/processed/credible_edges.csv` removed; references updated (README, docs)

---

## Decisions log (this slice)

- **Reframe over re-gate:** the binary credibility gate is replaced, not re-tuned. The audit showed the gate is misleading at available sample sizes; a measurement with explicit power context is the honest deliverable.
- **Approach A (rename in place):** repurpose `credible_edges.py` → `edge_report.py`; the old name encodes the verdict framing being abandoned. Reuses normalization; no dead empty CSV left behind.
- **Both power columns:** report `mde80_roi` (true detectability at 80% power) *and* `breakeven_needed_roi` (observed edge needed to clear the old CI gate). User chose "both" for completeness.
- **Continuous, no tiers:** numeric columns only, no categorical signal/underpowered/noise label. The reader judges from the numbers.
- **Normal-approx for power columns; exact/bootstrap retained for realized CI/p-value.** Stated explicitly to avoid being read as inconsistency.
- **Clamp bug scope:** fixed in derived ML (`moneyline.py`); the report's ML rows use real prices and aren't affected. Fixed because the derived report is still published and it's a real bug.
- **Cross-market comparability via ROI units:** all point estimates, CIs, and power columns expressed in ROI % so markets sit on one scale.
