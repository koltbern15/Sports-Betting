# NFL Betting Analytics

> Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

Slices 1–3 of the NFL Sports Betting Analytics Engine. Loads historical NFL games + closing lines from a Kaggle CSV into SQLite and produces three per-bucket historical-edge reports (against-the-spread, totals over/under, and derived moneyline) with full statistical rigor (n, win rate, ROI at -110/-105, p-value vs the 52.38% breakeven, Wilson 95% CI, and by-season trend). Slice 3 validates the derived-ML report against real historical sportsbook moneylines from nflverse (2020–2024).

See `docs/superpowers/specs/` for design documents and `docs/superpowers/plans/` for implementation plans. Slice 1 (ATS): `2026-05-26-nfl-betting-slice1-design.md` + `2026-05-26-nfl-betting-slice1.md`. Slice 2 (totals + moneyline): `2026-05-27-nfl-betting-slice2-design.md` + `2026-05-27-nfl-betting-slice2.md`. Slice 3 (real-line validation): `2026-05-27-nfl-betting-slice3-design.md` + `2026-05-27-nfl-betting-slice3.md`.

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

The largest bucket, `ml_small_fav` (n=562), shows derived +0.15% vs real **+1.03%** — a candidate for follow-up real-line slices. Derived prices systematically overshade underdogs (e.g., `ml_heavy_dog` derived ROI −22.75% vs real −9.62%, Δ +13.13 pp).

Caveat: 1,343 of 1,408 nflverse 2020–2024 games matched our DB; 65 playoff games (Wild Card week onward) are unmatched due to a week-numbering convention mismatch between Kaggle and nflverse — a follow-up could reconcile this.

## Scope

- **Slice 1 (complete):** ingestion, schema, statistics utilities, ATS-by-spread-bucket analysis.
- **Slice 2 (complete):** totals-by-line-bucket and moneyline-by-odds-bucket analysis (ML prices derived from spreads).
- **Slice 3 (complete):** real-line moneyline validation against nflverse 2020–2024. Heavy-fav +0.63% finding killed; small-fav real-line edge surfaced for follow-up.
- **Deferred to later slices:** live odds ingestion, best-bets engine, predictive modeling, interactive dashboard.
