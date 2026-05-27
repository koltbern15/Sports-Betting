# NFL Betting Analytics

> Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

Slice 1 of the NFL Sports Betting Analytics Engine. Loads historical NFL games + closing lines from a Kaggle CSV into SQLite and produces an ATS-by-spread-bucket report with full statistical rigor (n, win rate, ROI at -110/-105, p-value vs the 52.38% breakeven, Wilson 95% CI, and by-season trend).

See `docs/superpowers/specs/2026-05-26-nfl-betting-slice1-design.md` for the design and `docs/superpowers/plans/2026-05-26-nfl-betting-slice1.md` for the implementation plan.

## Setup

    uv sync

## Run tests

    uv run pytest -q

All tests should pass with zero failures.

## Lint

    uv run ruff check .

## Ingest data

1. Download `spreadspoke_scores.csv` from the Kaggle "NFL Scores and Betting Data" dataset.
2. Place it at `data/raw/spreadspoke_scores.csv`.
3. Run:

       uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv

   This populates `data/db/nfl_betting.sqlite`. Default season filter: 2004–2024. Re-running with the same CSV is idempotent.

## Generate the ATS report

    uv run python -m engine.ats

The command prints a per-bucket table to stdout and writes `data/processed/ats_by_bucket.csv`. The disclaimer appears in both outputs.

## Slice 1 scope

This slice covers ingestion, schema, statistics utilities, and the proof-of-concept ATS-by-spread-bucket analysis. Totals, moneyline, composites, regression, dashboards, and live odds are deferred to later slices.
