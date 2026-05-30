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

- [2026-05-26] **Don't forward-reference imports in TDD plans.** Plan T2 included `import math` in `engine/stats_utils.py` because it would be used in T5 (Wilson CI). Ruff (F401) flagged it as unused at T2. Fix: each task's code block should only import what that task uses; subsequent tasks add their own imports. When adding helper modules in incremental TDD, scope imports to the function being added.
- [2026-05-27] **Floating-point equality in tests must use pytest.approx.** Slice 2 T1 plan specified `assert m.roi_neg110 == 0.15` for dollar_weighted_roi with payouts `[1.30,-1.0,1.30,-1.0]`. Real result is `0.15000000000000002` due to float math. Fix: use `pytest.approx(0.15)`. When writing future plans involving sum/divide of floats, default to `pytest.approx` even when the math looks like it should land on a clean value.
- [2026-05-27] **Unused-import gotcha recurred in TEST file (Slice 2 T3).** Plan's test_moneyline.py included `import math` but never used it; ruff F401 flagged it. Same root cause as the 2026-05-26 entry, but in tests, not source. Fix: removed the unused import; tests still pass. When executing a TDD plan, scan import blocks against actual usage in BOTH source and test files before running ruff.
- [2026-05-27] **DB column names: use the schema, not the Kaggle CSV column names.** The Slice 2 plan drafted SQL queries with `b.total_line` and `g.score_home`/`g.score_away` — these are *Kaggle CSV* column names. The actual SQLite schema (engine/db.py) uses `b.total_close`, `g.home_score`, `g.away_score`. Both T7 and T9 implementer prompts had to be corrected before dispatch. Fix: when writing any plan that references DB queries, read engine/db.py for the schema first. The Kaggle column → DB column mapping happens in ingestion/loader.py.
- [2026-05-27] **derive_ml_from_spread must clamp probabilities at extreme spreads.** Real Kaggle data has games with spread_home_close as extreme as -26.5, where `p * 1.04762` overround pushes the implied probability above 1.0 and crashes `_prob_to_american`. Original fix (`_EPS=1e-6` clamp) silently produced -99,999,900 — still wrong. [2026-05-29] **Correct fix:** clamp to `_MAX_IMPLIED_PROB = 10000/10100` / `_MIN_IMPLIED_PROB = 100/10100` so derived prices floor near +/-10000 American and heavy-fav payouts stay realistic (> 0.001 per unit). Any new probability-to-American helper anywhere in the codebase must handle the same edge case.
- [2026-05-27] **ruff E741: single-char `l` is ambiguous in test/aggregator loops.** Pattern recurred in T7 and T9: per-season unpacking like `for season, (w, l) in groups` trips E741. Fix: use `losses` (or `losses_` if `losses` already exists in outer scope). Don't disable E741 — rename.
- [2026-05-27] **Appending imports mid-file causes ruff E402.** T9 plan said APPEND tests to test_validation.py, which caused new `import sqlite3` etc. to land after function definitions — ruff E402. Fix: always move new imports to the top-of-file import block when appending tests to an existing test file. Also fix: plan's test assertion `assert "ml_heavy_fav" in bucket_names or "ml_mid_fav" in bucket_names` assumed fixture spreads that don't produce those buckets; actual fixture spreads (-3.0, -7.0, -3.0, -0.5) produce ml_big_fav/ml_small_fav/ml_slight_fav/ml_pickem/ml_small_dog/ml_mid_dog. Verify bucket assertions against actual fixture data before writing plan tests.

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- [2026-05-29] **Slice 5 replaced the binary credible-edges gate with a continuous edge report + power/MDE columns** after an audit found the gate underpowered (Wilson-lower-bound gate needs +6-20% ROI to clear at available bucket sizes vs real edges of +1-3%).
- [2026-05-26] **Project decomposed into slices.** Full NFL betting analytics spec is too large for one design/plan. Decomposition: Slice 1 = ingestion + schema + stats_utils + one ATS analysis; Slice 2 = rest of Phase 2 analytics; Slice 3 = static report; Slice 4 = Streamlit dashboard; Slice 5+ = FastAPI/live odds. Each slice gets its own spec → plan → build cycle.
- [2026-05-26] **Data source: Kaggle "NFL Scores and Betting Data" CSV first; scrapers deferred.** Reason: legal, stable, no scraper fragility, gets math moving immediately. Pro-Football-Reference / SportsOddsHistory / Covers will be layered in for opens, moneylines, line movement in Slice 2+.
- [2026-05-26] **Dependency mgmt: `uv` (not pip+venv).** Faster, lockfile, modern. `pyproject.toml` is single source of truth.
- [2026-05-26] **Database: SQLite via stdlib `sqlite3`; no ORM.** Scale doesn't justify SQLAlchemy. Postgres deferred until SaaS-prod slice.
- [2026-05-26] **ATS push handling: pushes return stake (0 PnL), excluded from win-rate denominator, included in total bets denominator for ROI.**
