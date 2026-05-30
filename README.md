# NFL Betting Analytics

> Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

Slices 1–4 of the NFL Sports Betting Analytics Engine. Loads historical NFL games + closing lines from a Kaggle CSV into SQLite and produces three per-bucket historical-edge reports (against-the-spread, totals over/under, and derived moneyline) with full statistical rigor (n, win rate, ROI at -110/-105, p-value vs the 52.38% breakeven, Wilson 95% CI, and by-season trend). Slice 3 validates the derived-ML report against real historical sportsbook moneylines from nflverse (2020–2024). Slice 4 added per-season stability + bootstrap stats for ML. Slice 5 replaces the binary credible-edges gate with an honest cross-market `edge_report.csv`: every bucket is shown, ranked by point-estimate ROI, annotated with the smallest edge its sample size could detect.

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

## Scope

- **Slice 1 (complete):** ingestion, schema, statistics utilities, ATS-by-spread-bucket analysis.
- **Slice 2 (complete):** totals-by-line-bucket and moneyline-by-odds-bucket analysis (ML prices derived from spreads).
- **Slice 3 (complete):** real-line moneyline validation against nflverse 2020–2024. Heavy-fav +0.63% finding killed; small-fav real-line edge surfaced for follow-up.
- **Slice 4 (complete):** real-line statistical workup across all 3 markets; unified credible-edge ranker (binary gate; superseded by Slice 5).
- **Slice 5 (complete):** honest edge report — continuous metrics + power/MDE context replacing the binary gate; derived-ML clamp bug fixed.
- **Deferred to later slices:** closing-line-value (CLV) backtest (needs opening-line ingestion — not in current data), per-game-state filters, live odds + this-week pick generator, interactive dashboard.
