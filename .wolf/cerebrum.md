# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-05-26

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** sports-betting

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- [2026-05-26] **Project decomposed into slices.** Full NFL betting analytics spec is too large for one design/plan. Decomposition: Slice 1 = ingestion + schema + stats_utils + one ATS analysis; Slice 2 = rest of Phase 2 analytics; Slice 3 = static report; Slice 4 = Streamlit dashboard; Slice 5+ = FastAPI/live odds. Each slice gets its own spec → plan → build cycle.
- [2026-05-26] **Data source: Kaggle "NFL Scores and Betting Data" CSV first; scrapers deferred.** Reason: legal, stable, no scraper fragility, gets math moving immediately. Pro-Football-Reference / SportsOddsHistory / Covers will be layered in for opens, moneylines, line movement in Slice 2+.
- [2026-05-26] **Dependency mgmt: `uv` (not pip+venv).** Faster, lockfile, modern. `pyproject.toml` is single source of truth.
- [2026-05-26] **Database: SQLite via stdlib `sqlite3`; no ORM.** Scale doesn't justify SQLAlchemy. Postgres deferred until SaaS-prod slice.
- [2026-05-26] **ATS push handling: pushes return stake (0 PnL), excluded from win-rate denominator, included in total bets denominator for ROI.**
