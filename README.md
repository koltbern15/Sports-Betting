# NFL Betting Analytics

> Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

Slices 1–5 of the NFL Sports Betting Analytics Engine. Loads historical NFL games + closing lines from a Kaggle CSV into SQLite and produces three per-bucket historical-edge reports (against-the-spread, totals over/under, and derived moneyline) with full statistical rigor (n, win rate, ROI at -110/-105, p-value vs the 52.38% breakeven, Wilson 95% CI, and by-season trend). Slice 3 validates the derived-ML report against real historical sportsbook moneylines from nflverse (2020–2024). Slice 4 added per-season stability + bootstrap stats for ML. Slice 5 replaces the binary credible-edges gate with an honest cross-market `edge_report.csv`: every bucket is shown, ranked by point-estimate ROI, annotated with the smallest edge its sample size could detect.

See `docs/superpowers/specs/` for design documents and `docs/superpowers/plans/` for implementation plans. Slice 1 (ATS): `2026-05-26-nfl-betting-slice1-design.md` + `2026-05-26-nfl-betting-slice1.md`. Slice 2 (totals + moneyline): `2026-05-27-nfl-betting-slice2-design.md` + `2026-05-27-nfl-betting-slice2.md`. Slice 3 (real-line validation): `2026-05-27-nfl-betting-slice3-design.md` + `2026-05-27-nfl-betting-slice3.md`. Slice 4 (credible edges): `2026-05-27-nfl-betting-slice4-design.md` + `2026-05-27-nfl-betting-slice4.md`. Slice 5 (honest edge report): `2026-05-29-nfl-betting-slice5-design.md` + `2026-05-29-nfl-betting-slice5.md`.

## Setup

    uv sync

## Run tests

    uv run pytest -q

All tests should pass with zero failures.

## Lint

    uv run ruff check .

## Ingest data

1. Download the Kaggle "NFL Scores and Betting Data" dataset. It downloads as a ZIP archive containing `nfl_teams.csv`, `spreadspoke.R`, and `spreadspoke_scores.csv`. Extract the archive and keep `spreadspoke_scores.csv`.
2. Place it at `data/raw/spreadspoke_scores.csv`.
3. Run:

       uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv

   This populates `data/db/nfl_betting.sqlite`. Default season filter: 2004–2024. Re-running with the same CSV is idempotent.

## Generate the ATS report

    uv run python -m engine.ats

The command prints a per-bucket table to stdout and writes `data/processed/ats_by_bucket.csv`. The disclaimer appears in both outputs.

## Generate the totals report

    uv run python -m engine.totals

Prints a per-bucket over/under table to stdout and writes `data/processed/totals_by_bucket.csv`. Buckets: `total_le_39_5`, `total_40_42_5`, `total_43_45_5`, `total_46_48_5`, `total_49_51_5`, `total_ge_52`. The disclaimer appears in both outputs.

## Generate the moneyline report

    uv run python -m engine.moneyline

Prints a per-bucket moneyline table to stdout and writes `data/processed/moneyline_by_bucket.csv`. Buckets span heavy fav (≤ -300) through pickem (-109..+109) to heavy dog (≥ +300).

**Important caveat:** The Kaggle dataset does not contain historical sportsbook moneyline prices. This report **derives** ML prices from closing spreads using a standard NFL margin-of-victory model (normal CDF with σ ≈ 13.86) plus a -110/-110-equivalent vig. A derivation note is printed at the top of the output and included as a comment in the CSV. Findings reflect the spread market's efficiency expressed in moneyline form, not the moneyline market's independent efficiency. Real-time moneyline analysis is deferred to a future slice that pulls live odds.

## Slice 3 — Real-line moneyline validation

Validates Slice 2's derived-ML findings against real historical moneylines from nflverse (2020–2024).

    # fetch real ML (nflverse via nfl_data_py)
    uv run python -c "from ingestion.real_ml_source import fetch_real_ml; fetch_real_ml([2020,2021,2022,2023,2024]).to_csv('data/raw/real_ml_2020_2024.csv', index=False)"

    # load into DB
    uv run python -m ingestion.real_ml_loader data/raw/real_ml_2020_2024.csv

    # run validation
    uv run python -m engine.validation

Outputs price-level diagnostics + per-bucket ROI comparison (derived vs real). CSV written to `data/processed/ml_validation_report.csv`.

### Headline finding

The Slice 2 `ml_heavy_fav` headline (derived ROI +0.63%) does NOT hold under real prices. On the 2020–2024 nflverse sample (n=237 heavy-fav bets), derived ROI was +1.56% but real ROI was **−0.95%** — the apparent edge was an artifact of the spread→ML derivation.

**Update after audit fix:** the apparent `ml_small_fav` +1.03% real-ROI edge was an artifact of missing playoff games (Kaggle week 100–103 vs nflverse 18–22 numbering mismatch). After remapping (`fix(real_ml_source)` commit `16c555f`), all 1,408 games load. The corrected real ROI for `ml_small_fav` is **−0.36%** (n=588) — the edge is gone. Derived prices still systematically overshade underdogs (e.g., `ml_heavy_dog` derived −25.61% vs real −12.97%, Δ +12.64 pp).

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

## Slice 6 — Opening-line ingestion

Ingests historical NFL opening lines from two independent sources into the `opening_lines` table, then runs a data-quality audit.

**Sources:**

- **aussportsbetting (primary):** Manual-download xlsx from `https://www.aussportsbetting.com/data/historical-nfl-results-and-odds-data/`. Covers ~2006–2024 with spread, total, and opening ML (decimal odds converted to American). Sign convention matches our DB (negative = home favored). Download to `data/raw/aus_nfl.xlsx`.
- **SBR (cross-check):** SportsbookReviewsOnline, 2007–2021, spread + total. Fetched programmatically and cached to `data/raw/sbr_{season}.html`. Opening ML not available from SBR.

**Canonical source per season:** `aus` is canonical for 2013+ (richer: spread + total + ML); `sbr` is canonical for 2007–2012 (aus only covers back to ~2006 with matching games). Both sources coexist in the DB for the 2013–2021 overlap as cross-check counterparts.

**Workflow:**

    # Load both sources into the DB (idempotent; safe to re-run)
    uv run python scripts/load_opening_lines.py

    # Run the data-quality audit (writes docs/superpowers/notes/2026-05-29-opening-line-audit.md)
    uv run python scripts/cross_check_openers.py

**`opening_lines` schema:**

| column | type | notes |
| --- | --- | --- |
| `game_id` | TEXT | FK → games; part of PK |
| `source` | TEXT | `'sbr'` or `'aus'`; part of PK |
| `open_spread_home` | REAL | signed home perspective (negative = home fav) |
| `open_total` | REAL | game total |
| `open_ml_home` | INTEGER | American ML (null for SBR) |
| `open_ml_away` | INTEGER | American ML (null for SBR) |
| `source_url` | TEXT | source page URL |
| `collected_at` | TEXT | ISO timestamp of ingest |

**Audit headline (2026-05-29):**

- SBR: 3,476 rows inserted across 15 seasons (2007–2021), 1 unmatched.
- AUS: 5,144 rows inserted across 19 seasons (2006–2024), 287 unmatched (2025–2026 games not yet in the games table, as expected).
- Overlap agreement (2013–2021, 2,183 matched games): spread 61% within 0.5 pts / 75% within 1.0 pt; total 66% within 0.5 pts / 82% within 1.0 pt. The sub-100% agreement is expected — both sources capture independent opening snapshots; ~39% of games differ by 0.5–1.5 pts between sources, consistent with two aggregators capturing the opening line at slightly different timestamps.
- Closer sanity: mean spread movement open→close is +0.12 pts (healthy near-zero), stdev 1.72 pts. Total stdev is elevated (7.74 raw) due to one corrupted SBR `open_total` (541.0, a 2007 Chicago Bears game); excluding it, open→close total movement stdev is ~1.8 pts — healthy. AUS is canonical for 2013+ so CLV is unaffected.
- ML: AUS provides 5,144 opening ML rows; SBR provides 0 (not published). ML is back in via aussportsbetting.

## Slice 7 — CLV engine + validation

Computes per-game closing-line value (CLV) for spread and total markets, grades reference bets at the opener, buckets by CLV, and validates whether positive CLV predicts covering the opening number.

**CLV definitions:**

- `clv_spread = open_spread_home - close_spread_home` — positive means the close moved toward the home side (you opened on the sharp side of the home bet)
- `clv_total = close_total - open_total` — positive means the close moved up (favoring the over)

**Reference bets:** one per game per market — HOME at opener for spread, OVER at opener for total. Graded at the opening number, not the close.

**Workflow:**

    uv run python -m engine.clv

Prints a per-bucket table to stdout and writes `data/processed/clv_report.csv`.

**`clv_report.csv` columns:**

| column | description |
|---|---|
| `market` | `spread` or `total` |
| `clv_bucket` | `clv_le_neg2`, `clv_neg2_neg05`, `clv_pm05`, `clv_05_2`, `clv_gt_2` |
| `n` | bets in bucket (pushes included in n, excluded from win_rate) |
| `mean_clv` | average CLV in points for bets in this bucket |
| `win_rate` | fraction of non-push bets that covered the opener |
| `roi` | ROI at -110 odds (all bets including pushes in denominator) |
| `ci_low` / `ci_high` | 95% Wilson CI on win rate, expressed in ROI units |
| `p_value` | one-sided binomial p-value vs 52.38% breakeven |
| `profitable_seasons_pct` | fraction of seasons where this bucket was profitable |
| `mde80` | smallest true ROI edge detectable at 80% power for this n |
| `breakeven_needed` | observed ROI needed for 95% CI lower bound to clear breakeven |

**Headline finding (2026-05-30):** Win rate rises **perfectly monotonically** with CLV in both markets (spread: 39.9% → 44.7% → 51.9% → 55.3% → 57.6%; total: 36.4% → 47.4% → 51.7% → 53.9% → 57.2%). Positive-CLV buckets (`clv_05_2`, `clv_gt_2`) clear the 52.38% breakeven in both markets. The close is sharper than the open in this data — but this is a **signal test, not a strategy**: CLV is unknown until the line closes.

See `docs/superpowers/notes/2026-05-30-clv-findings.md` for the full analysis including power assessment and ML follow-on recommendation.

## Scope

- **Slice 1 (complete):** ingestion, schema, statistics utilities, ATS-by-spread-bucket analysis.
- **Slice 2 (complete):** totals-by-line-bucket and moneyline-by-odds-bucket analysis (ML prices derived from spreads).
- **Slice 3 (complete):** real-line moneyline validation against nflverse 2020–2024. Heavy-fav +0.63% finding killed; small-fav real-line edge surfaced for follow-up.
- **Slice 4 (complete):** real-line statistical workup across all 3 markets; unified credible-edge ranker (binary gate; superseded by Slice 5).
- **Slice 5 (complete):** honest edge report — continuous metrics + power/MDE context replacing the binary gate; derived-ML clamp bug fixed.
- **Slice 6 (complete):** historical opening-line ingestion (aussportsbetting + SBR) into `opening_lines`, with a full data-quality audit. Foundation for CLV (Slice 7).
- **Slice 7 (complete):** CLV engine — per-game CLV (spread+total) + validation of whether positive CLV predicts covering the opener; honest-metrics shape. Signal test, not a strategy.
- **Deferred to later slices:** ML-CLV extension (Slice 8 candidate), per-game-state filters, live odds + this-week pick generator, interactive dashboard.
