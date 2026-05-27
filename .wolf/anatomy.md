# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-05-27T15:17:50.190Z
> Files: 34 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.gitignore` — Git ignore rules (~81 tok)
- `CLAUDE.md` — OpenWolf (~57 tok)
- `pyproject.toml` — NFL historical betting analytics engine (Slice 1: ingestion + ATS) (~142 tok)
- `README.md` — Project documentation (~389 tok)

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

## docs/superpowers/plans/

- `2026-05-26-nfl-betting-slice1.md` — NFL Betting Analytics — Slice 1 Implementation Plan (~23728 tok)
- `2026-05-27-nfl-betting-slice2.md` — NFL Betting Analytics — Slice 2 Implementation Plan (~17122 tok)

## docs/superpowers/specs/

- `2026-05-26-nfl-betting-slice1-design.md` — NFL Betting Analytics — Slice 1 Design (~3979 tok)
- `2026-05-27-nfl-betting-slice2-design.md` — NFL Betting Analytics — Slice 2 Design (~2942 tok)

## engine/

- `__init__.py` (~0 tok)
- `ats.py` — ATS-by-spread-bucket analysis. (~1066 tok)
- `bucket_analysis.py` — Shared bucket-analysis machinery used by ATS, totals, and moneyline modules. (~1253 tok)
- `db.py` — SQLite connection + schema management for the betting analytics DB. (~803 tok)
- `stats_utils.py` — Pure statistics utilities for sports-betting analysis. (~1070 tok)

## ingestion/

- `__init__.py` (~0 tok)
- `divisions.py` — Static NFL division lookup (2002 realignment, valid 2002–present). (~614 tok)
- `loader.py` — CSV → SQLite loader for NFL betting data. (~3186 tok)
- `stadiums.py` — Stadium dome-flag lookup. (~346 tok)
- `team_names.py` — Historical NFL team name normalization (covers 2004–2024 window). (~786 tok)

## tests/

- `__init__.py` (~0 tok)
- `conftest.py` — memory_db, fixtures_dir, tmp_db_path (~153 tok)
- `test_ats.py` — test_bucket_spread_known_values, test_bucket_spread_none_returns_none, test_metrics_basic_case, test (~1977 tok)
- `test_bucket_analysis.py` — Smoke tests for the shared bucket-analysis helpers. (~646 tok)
- `test_db.py` — test_init_schema_creates_three_tables, test_init_schema_is_idempotent, test_init_schema_seeds_team_d (~516 tok)
- `test_loader_helpers.py` — test_home_favored, test_away_favored, test_pickem_returns_zero, test_missing_spread_returns_none (~1728 tok)
- `test_loader.py` — loaded_db, test_load_report_counts, test_load_creates_all_5_games, test_load_creates_all_5_lines (~1318 tok)
- `test_static_data.py` — test_divisions_has_32_teams, test_divisions_has_8_divisions_with_4_teams_each, test_division_of_know (~826 tok)
- `test_stats_utils.py` — test_american_to_decimal_negative, test_american_to_decimal_positive, test_decimal_to_american_negat (~1494 tok)

## tests/fixtures/

- `games_20_ats.csv` — 20-game ATS fixture (2 groups: favorite spreads -9.5 to -2.0, PICK lines, dog spreads). Line counts verified. (~651 tok)
- `games_5.csv` — 5-game loader fixture: KC/NO, GB/MIN, HOU/CHI, BUF/PIT, ATL/PIT. Covers all derivations. (~207 tok)
