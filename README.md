# NFL Betting Analytics

> Past performance does not guarantee future results. This tool is for informational purposes only. Gamble responsibly.

Slice 1: ingestion + SQLite schema + statistics utilities + ATS-by-spread-bucket analysis.

See `docs/superpowers/specs/2026-05-26-nfl-betting-slice1-design.md` for the design.

## Setup

```powershell
uv sync
```

## Run tests

```powershell
uv run pytest
```

## Ingest data (Slice 1: Kaggle CSV only)

Place `spreadspoke_scores.csv` into `data/raw/` (Kaggle "NFL Scores and Betting Data").

```powershell
uv run python -m ingestion.loader data/raw/spreadspoke_scores.csv
```

## Generate the ATS report

```powershell
uv run python -m engine.ats
```

Output: pretty-printed table to stdout and `data/processed/ats_by_bucket.csv`.
