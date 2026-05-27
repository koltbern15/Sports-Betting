# NFL Betting Analytics

> Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

Slices 1 and 2 of the NFL Sports Betting Analytics Engine. Loads historical NFL games + closing lines from a Kaggle CSV into SQLite and produces three per-bucket historical-edge reports (against-the-spread, totals over/under, and derived moneyline) with full statistical rigor (n, win rate, ROI at -110/-105, p-value vs the 52.38% breakeven, Wilson 95% CI, and by-season trend).

See `docs/superpowers/specs/` for design documents and `docs/superpowers/plans/` for implementation plans. Slice 1 (ATS): `2026-05-26-nfl-betting-slice1-design.md` + `2026-05-26-nfl-betting-slice1.md`. Slice 2 (totals + moneyline): `2026-05-27-nfl-betting-slice2-design.md` + `2026-05-27-nfl-betting-slice2.md`.

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

## Scope

- **Slice 1 (complete):** ingestion, schema, statistics utilities, ATS-by-spread-bucket analysis.
- **Slice 2 (complete):** totals-by-line-bucket and moneyline-by-odds-bucket analysis (ML prices derived from spreads).
- **Deferred to later slices:** live odds ingestion, best-bets engine, predictive modeling, interactive dashboard.
