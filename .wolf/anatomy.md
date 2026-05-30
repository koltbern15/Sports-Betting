# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-05-30T02:29:40.806Z
> Files: 19 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `README.md` — Project documentation (~2830 tok)

## .claude/


## .claude/rules/


## data/db/


## data/processed/


## data/raw/


## docs/superpowers/notes/

- `2026-05-29-opening-line-probe.md` — Opening-Line Source Probe — 2026-05-29 (~2221 tok)

## docs/superpowers/plans/

- `2026-05-29-nfl-betting-slice6.md` — NFL Betting Analytics — Slice 6: Opening-Line Ingestion — Implementation Plan (~10502 tok)

## docs/superpowers/specs/

- `2026-05-29-nfl-betting-slice6-design.md` — NFL Betting Analytics — Slice 6: Opening-Line Ingestion (full audit) (~3573 tok)

## engine/

- `db.py` — SQLite connection + schema management for the betting analytics DB. (~1023 tok)
- `opener_audit.py` — Pure audit math for opening-line data quality. No I/O. (~395 tok)

## ingestion/

- `opening_line_aus.py` — Parse the Australia Sports Betting NFL xlsx into OpeningLineRecords. (~910 tok)
- `opening_line_common.py` — Shared types + pure normalization helpers for opening-line ingestion. (~648 tok)
- `opening_line_loader.py` — Load OpeningLineRecords into the opening_lines table. (~792 tok)
- `opening_line_sbr.py` — Parse SportsbookReviewsOnline (SBR) NFL season odds pages into records. (~2207 tok)

## scripts/

- `cross_check_openers.py` — Opening-line data quality audit. (~2292 tok)
- `load_opening_lines.py` — Load opening lines from all sources into the opening_lines DB table. (~1094 tok)

## tests/

- `test_db.py` — test_init_schema_creates_all_tables, test_init_schema_is_idempotent, test_init_schema_seeds_team_div (~1235 tok)
- `test_opener_audit.py` — Tests for engine.opener_audit — pure audit math on synthetic data. (~327 tok)
- `test_opening_line_aus.py` — Tests for ingestion.opening_line_aus — parse the xlsx fixture. (~323 tok)
- `test_opening_line_common.py` — Tests for ingestion.opening_line_common — pure record + normalization helpers. (~586 tok)
- `test_opening_line_loader.py` — Tests for ingestion.opening_line_loader — join + insert vs in-memory DB. (~1003 tok)
- `test_opening_line_sbr.py` — Tests for ingestion.opening_line_sbr — parse the SBR HTML fixture (offline). (~715 tok)

## tests/fixtures/

- `sbr_sample.html` — SBR sample fixture (NFL 2021-22) (~564 tok)
