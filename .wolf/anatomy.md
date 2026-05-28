# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-05-28T00:53:28.498Z
> Files: 57 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.gitignore` — Git ignore rules (~81 tok)
- `CLAUDE.md` — OpenWolf (~57 tok)
- `pyproject.toml` — NFL historical betting analytics engine (Slice 1: ingestion + ATS) (~142 tok)
- `README.md` — Project documentation (~1916 tok)

## .claude/

- `settings.json` (~441 tok)

## .claude/rules/

- `openwolf.md` (~313 tok)

## data/db/

- `.gitkeep` (~0 tok)

## data/processed/

- `.gitkeep` (~0 tok)

## data/raw/

- `.gitkeep` (~0 tok)

## docs/superpowers/notes/

- `2026-05-27-nflverse-probe.md` — nflverse import_schedules probe — 2026-05-27 (~1253 tok)
- `2026-05-28-kaggle-nflverse-crosscheck.md` — Kaggle vs nflverse closing-line cross-check — 2026-05-28 (~865 tok)

## docs/superpowers/plans/

- `2026-05-26-nfl-betting-slice1.md` — NFL Betting Analytics — Slice 1 Implementation Plan (~23728 tok)
- `2026-05-27-nfl-betting-slice2.md` — NFL Betting Analytics — Slice 2 Implementation Plan (~17122 tok)
- `2026-05-27-nfl-betting-slice3.md` — NFL Betting Analytics — Slice 3 Implementation Plan (~14829 tok)
- `2026-05-27-nfl-betting-slice4.md` — NFL Betting Analytics — Slice 4 Implementation Plan (~12608 tok)

## docs/superpowers/specs/

- `2026-05-26-nfl-betting-slice1-design.md` — NFL Betting Analytics — Slice 1 Design (~3979 tok)
- `2026-05-27-nfl-betting-slice2-design.md` — NFL Betting Analytics — Slice 2 Design (~2942 tok)
- `2026-05-27-nfl-betting-slice3-design.md` — NFL Betting Analytics — Slice 3: Real-Line Moneyline Validation (~2693 tok)
- `2026-05-27-nfl-betting-slice4-design.md` — NFL Betting Analytics — Slice 4: Real-Line Statistical Workup + Credible Edges Ranker (~2477 tok)

## engine/

- `__init__.py` (~0 tok)
- `ats.py` — ATS-by-spread-bucket analysis. (~1066 tok)
- `bucket_analysis.py` — Shared bucket-analysis machinery used by ATS, totals, and moneyline modules. (~1548 tok)
- `credible_edges.py` — Cross-market credible-edges ranker. (~2135 tok)
- `db.py` — SQLite connection + schema management for the betting analytics DB. (~892 tok)
- `moneyline.py` — Moneyline-by-odds-bucket analysis (prices derived from closing spreads). Includes DERIVATION_NOTE + _main CLI (writes data/processed/moneyline_by_bucket.csv with derivation-note comment header above disclaimer). (~2167 tok)
- `stats_utils.py` — Pure statistics utilities for sports-betting analysis. (~1543 tok)
- `totals.py` — Totals-by-line-bucket analysis: BUCKET_ORDER_TOTALS + bucket_total + TotalsReport + totals_by_line_bucket aggregator + _main CLI (writes data/processed/totals_by_bucket.csv). (~869 tok)
- `validation.py` — Real-line moneyline validation — comparator + reporting. (~3308 tok)

## ingestion/

- `__init__.py` (~0 tok)
- `divisions.py` — Static NFL division lookup (2002 realignment, valid 2002–present). (~614 tok)
- `loader.py` — CSV → SQLite loader for NFL betting data. (~3186 tok)
- `real_ml_loader.py` — Loader for real historical moneylines into the real_ml_lines table. (~1535 tok)
- `real_ml_source.py` — Tier-1 real moneyline data source — nflverse via nfl_data_py. (~743 tok)
- `stadiums.py` — Stadium dome-flag lookup. (~346 tok)
- `team_codes.py` — nflverse team abbreviation → canonical full-name mapping. (~508 tok)
- `team_names.py` — Historical NFL team name normalization (covers 2004–2024 window). (~786 tok)

## scripts/

- `cross_check_ats_totals.py` — One-time Kaggle-vs-nflverse cross-check for closing spread + total lines. (~1375 tok)

## tests/

- `__init__.py` (~0 tok)
- `conftest.py` — memory_db, fixtures_dir, tmp_db_path (~153 tok)
- `test_ats.py` — test_bucket_spread_known_values, test_bucket_spread_none_returns_none, test_metrics_basic_case, test (~1977 tok)
- `test_bucket_analysis.py` — Smoke tests for the shared bucket-analysis helpers. (~1077 tok)
- `test_credible_edges.py` — Tests for engine.credible_edges — pure ranker tested with synthetic CSVs. (~1941 tok)
- `test_db.py` — test_init_schema_creates_four_tables, test_init_schema_is_idempotent, test_init_schema_seeds_team_di (~780 tok)
- `test_loader_helpers.py` — test_home_favored, test_away_favored, test_pickem_returns_zero, test_missing_spread_returns_none (~1728 tok)
- `test_loader.py` — loaded_db, test_load_report_counts, test_load_creates_all_5_games, test_load_creates_all_5_lines (~1318 tok)
- `test_moneyline.py` — Tests for engine.moneyline. (~1639 tok)
- `test_real_ml_loader.py` — Tests for ingestion.real_ml_loader — parse + validate helpers. (~1329 tok)
- `test_real_ml_source.py` — Tests for ingestion.real_ml_source — nflverse fetcher with mocked HTTP. (~805 tok)
- `test_static_data.py` — test_divisions_has_32_teams, test_divisions_has_8_divisions_with_4_teams_each, test_division_of_know (~1056 tok)
- `test_stats_utils.py` — test_american_to_decimal_negative, test_american_to_decimal_positive, test_decimal_to_american_negat (~1976 tok)
- `test_totals.py` — Tests for engine.totals. (~819 tok)
- `test_validation.py` — Tests for engine.validation — pure helpers. (~1973 tok)

## tests/fixtures/

- `games_20_ats.csv` — 20-game ATS fixture (2 groups: favorite spreads -9.5 to -2.0, PICK lines, dog spreads). Line counts verified. (~651 tok)
- `games_5.csv` — 5-game loader fixture: KC/NO, GB/MIN, HOU/CHI, BUF/PIT, ATL/PIT. Covers all derivations. (~207 tok)
- `moneyline_20.csv` — 20-game moneyline fixture spanning all 11 derived ML buckets. Bet-row counts (40 total): heavy_fav 9, mid_fav 6, small_fav 3, slight_fav 4, slight_dog 3, small_dog 3, mid_dog 3, big_dog 3, heavy_dog 6 (big_fav and pickem are 0). (~652 tok)
- `real_ml_5.csv` (~100 tok)
- `totals_20.csv` — 20-game totals fixture spanning all 6 total buckets (38/41/44/47/50/53). 11 overs + 7 unders + 2 pushes. (~651 tok)
