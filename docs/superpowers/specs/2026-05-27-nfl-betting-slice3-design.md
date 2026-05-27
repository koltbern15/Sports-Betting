# NFL Betting Analytics — Slice 3: Real-Line Moneyline Validation

**Date:** 2026-05-27
**Status:** Approved (brainstorming complete)
**Predecessor:** Slice 2 (`docs/superpowers/specs/2026-05-27-nfl-betting-slice2-design.md`)
**Implementation plan:** `docs/superpowers/plans/2026-05-27-nfl-betting-slice3.md` (to be written)

---

## Goal

Validate the Slice 2 finding that the `ml_heavy_fav` bucket shows **+0.63% ROI** (n=1,125, p≈0) by comparing the **derived** moneyline prices (Slice 2's `derive_ml_from_spread`) against **real historical sportsbook** moneyline prices on a 2020–2024 sample.

The Slice 2 number is built on prices we *derived* from closing spreads via normal-CDF + vig (`SIGMA=13.86`, `OVERROUND=1.04762`). If those derived prices systematically over- or under-state the prices the market actually charged, the +0.63% could be an artifact of the derivation, not a real edge. Slice 3 either confirms or kills that finding before any downstream slice (static report, dashboard, live odds) is built on top of it.

## Out of scope (deferred)

- Full historical scrape (pre-2020) — if 2020–2024 validation succeeds, extending back is a follow-up.
- Real-line validation for ATS or totals — same machinery generalizes once the ML case is proven.
- Replacing derived ML with real ML in the main analysis pipeline.
- Live-odds integration.

---

## Architecture

**Pure-function discipline preserved** — the comparison logic is a single function `compare_ml_prices(conn) → ValidationReport` operating on dataframes; testable in isolation with fixtures, no I/O coupling.

**New SQLite table** `real_ml_lines`:

| column | type | notes |
|---|---|---|
| `game_id` | INTEGER PRIMARY KEY | FK to `games.id` |
| `ml_home_real` | INTEGER | American odds, e.g. `-350` or `+275`. Nullable (blank = data not found). |
| `ml_away_real` | INTEGER | Same. Nullable. |
| `source` | TEXT | e.g. `"nflverse"`, `"sportsoddshistory"` |
| `source_url` | TEXT | Nullable; helpful for spot-auditing |
| `collected_at` | TEXT | ISO timestamp |

Kept separate from `betting_lines` because most games will never have real ML, this is one-off validation data, and it leaves Slice 1/2 code untouched.

**Derived ML is recomputed on the fly** via `derive_ml_from_spread` — deterministic, no storage needed.

**Data acquisition uses a priority ladder** — try programmatic sources first, fall back only on failure. The selected source is recorded in `real_ml_lines.source` per row.

---

## Data acquisition — priority ladder

| Tier | Source | Effort | Outcome |
|---|---|---|---|
| **1** | `nfl_data_py` (Python wrapper for nflverse releases) — `import_sc_lines(2020, 2024)` or equivalent | `uv add nfl-data-py`; one function call | Validates **all** ml buckets across 2020–2024 (~1,400 games), not just heavy_fav. |
| **2** | Direct download from `nflverse-data` GitHub releases | One HTTP GET per season CSV | Same data without the Python dep. |
| **3** | Scrape SportsOddsHistory.com season pages | Light scraper: `httpx` + `selectolax`; respect robots.txt, single-pass with on-disk cache, 2s/page rate limit | Per-season HTML tables → DataFrame. |
| **4** | Manual hand-collection (CSV from `scripts/select_validation_sample.py` lookup checklist) | 150 rows by hand | Last resort only. |

**Implementation plan T1** must execute a tier-1 probe before any other work: pip-install `nfl_data_py`, attempt the data fetch, inspect columns. Outcome of T1 determines whether tiers 2/3 are needed.

**Authorization:** Slice 3 implementation may execute the tier ladder autonomously without per-tier user approval. Stop and ask only if data shape requires a design decision (e.g., source has *opening* ML but not *closing*).

---

## Components

| File | Purpose | Lifecycle |
|---|---|---|
| `engine/db.py` | Add `real_ml_lines` to `init_schema` | MODIFY |
| `ingestion/real_ml_source.py` | `fetch_real_ml(seasons: list[int]) → pd.DataFrame` — encapsulates tier 1→4 logic | NEW |
| `ingestion/real_ml_loader.py` | Joins fetched data to `games` by `(season, week, home, away)`, upserts `real_ml_lines`; idempotent | NEW |
| `engine/validation.py` | `compare_ml_prices()` + `ValidationReport` dataclass + CLI entry | NEW |
| `scripts/select_validation_sample.py` | Tier-4 only: produces 150-row CSV lookup checklist | NEW (conditional — only if tiers 1–3 fail) |
| `tests/fixtures/real_ml_5.csv` | Hand-built 5-game fixture | NEW |
| `tests/test_validation.py` | Tests for `compare_ml_prices` | NEW |
| `tests/test_real_ml_source.py` | Mocks HTTP layer; verifies column mapping | NEW |
| `README.md` | "Slice 3 — Real-line validation" section | MODIFY |

---

## End-to-end workflow (automated path)

```
1. uv run python -m ingestion.real_ml_source --seasons 2020 2021 2022 2023 2024
   → fetches real ML via tier-1 source, writes data/raw/real_ml_2020_2024.csv

2. uv run python -m ingestion.real_ml_loader data/raw/real_ml_2020_2024.csv
   → joins to games table, upserts real_ml_lines (idempotent)

3. uv run python -m engine.validation
   → prints price-level + bucket-ROI tables;
     writes data/processed/ml_validation_report.csv with disclaimer
```

If tier 1–3 all fail, fall back to:

```
1. uv run python scripts/select_validation_sample.py
   → writes data/processed/validation_sample.csv (150-row checklist with blank
     ml_home_real / ml_away_real columns)

2. [Manual] Open the CSV in a spreadsheet, fill ml_home_real / ml_away_real
   from SportsOddsHistory, save back to the same path.

3. uv run python -m ingestion.real_ml_loader data/processed/validation_sample.csv
4. uv run python -m engine.validation
```

(Loader accepts both the automated `data/raw/real_ml_2020_2024.csv` and the manual `data/processed/validation_sample.csv` — column names are aligned across both paths.)

---

## Validation outputs

**Price-level block** — computed **per betting side** (each game produces 2 rows: home side, away side), so a 250-game sample produces up to 500 comparisons. For each side, convert both real and derived American ML to implied probability (raw, vig included) and compute:

- `error_prob = real_implied_p − derived_implied_p` (in probability points; e.g., `+0.02` = real market priced the team 2 percentage points higher than the model)
- `error_ml = real_ml − derived_ml` (raw American-odds delta; reported alongside `error_prob` for human readability)

Aggregate stats reported:

- `mean_error_prob`, `median_abs_error_prob`
- `pct_within_2_pct_points` — share of sides where `|error_prob| ≤ 0.02`
- `pct_sign_flip` — share of sides where `sign(real_implied_p − 0.5) ≠ sign(derived_implied_p − 0.5)` (i.e., real says favorite, derived says dog or vice versa)
- `derived_overshades_favorites` — boolean, true if `mean_error_prob > 0` on favorite sides AND >60% of favorite sides share that sign (i.e., model is systematically pricing favorites as more likely to win than the market does)

**Bucket-ROI block** — recompute ROI on the same sample under each price set:

| bucket | n | derived_roi | real_roi | delta_roi | derived_wins | derived_losses | real_wins | real_losses |

Only buckets with `n ≥ 30` (low-sample threshold from Slice 1) get reported.

**CSV output** includes both blocks plus comment-line disclaimer matching Slice 2 conventions, with an extra comment line: `# Real-line sample: source=<source>, seasons=2020-2024, n=<n>`.

---

## Error handling

- Tier-1 probe failure (import error, empty response, missing required column) → log + advance to tier 2.
- Loader: each row independently validated; bad rows (unparseable American odds, missing required field) logged and skipped, don't kill the load.
- Validation engine: if `real_ml_lines` is empty or total sample < 30, refuse to print bucket-ROI table — exit with explicit "insufficient validation data" message. Price-level block still runs if any data exists.
- All file I/O uses `pathlib` + `utf-8` encoding (Slice 2 convention).

---

## Testing

- **`tests/fixtures/real_ml_5.csv`** — 5 hand-built rows covering: derived = real exactly, derived more negative than real (overshade), derived less negative, sign-flip case, missing `real_ml_fav` (blank).
- **`tests/test_validation.py`** — ~7 tests:
  - `mean_error_prob` and `median_abs_error_prob` match hand-calc
  - sign-flip count matches hand-calc
  - blanks excluded from real_n
  - ROI deltas computed correctly under both price sets
  - empty `real_ml_lines` → raises or returns sentinel report
  - low-sample bucket gets `*` marker and excluded ROI per Slice 1 convention
  - join-mismatch (real_ml row with no matching game_id) → skipped + logged
- **`tests/test_real_ml_source.py`** — ~3 tests:
  - tier-1 mock returns expected DataFrame schema
  - tier-1 failure routes to tier 2 (mocked)
  - column-name mapping handles known nflverse variants

Target: ~10 new tests, ~201 total passing.

---

## Definition of Done

- [ ] `real_ml_lines` table exists in `engine/db.py.init_schema` (schema migration safe for the existing DB)
- [ ] `ingestion/real_ml_source.py` exists, tier 1 probe documented in commit message or code comment
- [ ] `ingestion/real_ml_loader.py` is idempotent (re-run keeps row count stable)
- [ ] `engine/validation.py` produces two tables (price-level + bucket-ROI) and writes `data/processed/ml_validation_report.csv` with comment-line disclaimer + source note
- [ ] `tests/fixtures/real_ml_5.csv` and `tests/test_validation.py` exist with ~7 passing tests
- [ ] `tests/test_real_ml_source.py` exists with ~3 passing tests (HTTP layer mocked)
- [ ] `uv run pytest -q` shows ~200+ tests passing
- [ ] `uv run ruff check .` clean
- [ ] Real-data smoke: validation report runs against ≥250 heavy-fav games from 2020–2024 (or full fallback path completed)
- [ ] README has "Slice 3 — Real-line validation" section explaining the workflow
- [ ] Slice 3 milestone tag `slice3-complete` cut
- [ ] Findings logged: write a one-paragraph summary to `.wolf/memory.md` stating whether the +0.63% holds, vanishes, or grows under real prices

---

## Decisions log (this slice)

- **Validation method:** price-level diagnostics + bucket-ROI comparison (Option C from brainstorm). Price-level is the diagnostic, bucket-ROI is the headline.
- **Sample selection (manual fallback only):** recent (2020–2024), random 150, seeded for reproducibility.
- **Data source priority:** programmatic first (nflverse → direct download → scrape), manual last. Authorized to traverse autonomously.
- **Separate table over schema extension:** `real_ml_lines` is its own table, not new columns on `betting_lines`, because most games never have real ML and we don't want to pollute the main schema with one-off validation data.
- **Derived ML recomputed on the fly** rather than stored — `derive_ml_from_spread` is deterministic.
