# NFL Betting Analytics — Slice 6: Opening-Line Ingestion (full audit)

**Date:** 2026-05-29
**Status:** Approved (brainstorming complete)
**Predecessor:** Slice 5 (`docs/superpowers/specs/2026-05-29-nfl-betting-slice5-design.md`)
**Implementation plan:** `docs/superpowers/plans/2026-05-29-nfl-betting-slice6.md` (to be written)
**Successor (planned):** Slice 7 — CLV engine + analysis (built on this slice's data)

---

## Why this slice

The Slice 5 audit concluded that any future +EV signal needs higher statistical power than static bucket win-rates — closing-line value (CLV) being the canonical example, because it measures price movement per bet rather than waiting on binary outcomes. CLV requires **opening** lines paired with closing lines. The project has only closing lines (Kaggle `spread_favorite`/`over_under_line`; nflverse `spread_line`/`total_line`/moneyline). A research sweep confirmed no opening lines exist in nflverse or the Kaggle file, but two **free** sources do publish historical openers:

- **SportsbookReviewsOnline (SBR):** opening + closing spread/total per game, 2007–2021, scrapeable HTML (robots.txt permits).
- **Australia Sports Betting (aussportsbetting):** opening spread/total (and possibly moneyline) per game, 2013–2024, free `.xlsx` download.

This slice ingests both, lands them in the database, and **audits** them so the CLV slice rests on verified data. It does **not** compute CLV — that is Slice 7.

## Goal

Produce trustworthy historical NFL opening lines (spread + total, moneyline if available) in the database, drawn from both free sources, with a full data-quality audit: cross-source agreement in the overlap, sanity vs existing closers, coverage, and outliers — written up in a findings note.

## Markets (decided)

- **Committed:** opening **spread** and **total** (solid from both sources).
- **Bonus:** opening **moneyline** — populated only if the probe (Task 1) confirms aussportsbetting carries clean opening ML. The schema includes nullable ML columns regardless; if the probe finds no usable ML, those columns stay null and ML is deferred to a later slice. No wasted effort either way.

## Validation depth (decided: full audit)

Load both sources, plus: (1) cross-validate the two sources' openers agree in the 2013–2021 overlap, (2) sanity-check openers against existing closers, (3) per-source coverage, (4) per-source line-by-line disagreement + outlier detection, all written into a findings doc like `docs/superpowers/notes/2026-05-28-kaggle-nflverse-crosscheck.md`.

## Out of scope (deferred to Slice 7)

- Any CLV computation, line-movement modeling, signal testing, or edge-report integration.
- Opening moneyline if the probe finds it absent/unusable.
- Pre-2007 openers (no free source verified) and any paid source.
- Intraday line-movement time series (these sources give open + close only, no timestamps).

---

## Architecture

**Additive.** Mirrors the existing `ingestion/` split (one responsibility per module), parallel to how `loader.py`, `real_ml_source.py`, and `real_ml_loader.py` already divide fetch / normalize / load.

**Probe-first.** Task 1 is a verification probe (like the nflverse probe before Slice 3). Its outcome — aussportsbetting's exact columns and ML presence, SBR's table layout and the spread/total column-interleave — confirms the parse strategy and the ML decision before the real scrapers are built.

### Components

| File | Responsibility | Lifecycle |
|---|---|---|
| `docs/superpowers/notes/2026-05-29-opening-line-probe.md` | Probe findings: source structure, columns, ML presence, parse strategy | NEW |
| `engine/db.py` | Add `opening_lines` table + index to the schema | MODIFY |
| `tests/test_db.py` | Tests for the new table (creation, idempotency) | MODIFY |
| `ingestion/opening_line_sbr.py` | Fetch + parse SBR per-season HTML → normalized `OpeningLineRecord`s | NEW |
| `tests/test_opening_line_sbr.py` | Parser tests against a saved SBR HTML fixture | NEW |
| `ingestion/opening_line_aus.py` | Download + parse aussportsbetting `.xlsx` → normalized `OpeningLineRecord`s | NEW |
| `tests/test_opening_line_aus.py` | Parser tests against a saved xlsx fixture | NEW |
| `ingestion/opening_line_loader.py` | Join records to `games`, insert into `opening_lines`, report unmatched; expose canonical-opener precedence helper | NEW |
| `tests/test_opening_line_loader.py` | Loader tests against in-memory DB | NEW |
| `scripts/cross_check_openers.py` | Full audit: overlap agreement, closer sanity, coverage, outliers; writes findings note | NEW |
| `docs/superpowers/notes/2026-05-29-opening-line-audit.md` | Audit findings (written by the cross-check run) | NEW |
| `pyproject.toml` | Add `openpyxl` (xlsx) + `lxml` (pandas `read_html`) | MODIFY |
| `tests/fixtures/` | Small saved SBR HTML + aussportsbetting xlsx samples | NEW |
| `README.md` | Slice 6 section + opening-line workflow | MODIFY |

**No changes to existing engine analysis modules.**

---

## Schema

New table, separate from `betting_lines` (mirrors `real_ml_lines` being its own table). Composite key `(game_id, source)` so both sources' openers for the same game coexist for cross-validation.

```sql
CREATE TABLE IF NOT EXISTS opening_lines (
    game_id          TEXT NOT NULL REFERENCES games(game_id),
    source           TEXT NOT NULL CHECK (source IN ('sbr','aus')),
    open_spread_home REAL,
    open_total       REAL,
    open_ml_home     INTEGER,
    open_ml_away     INTEGER,
    source_url       TEXT,
    collected_at     TEXT,
    PRIMARY KEY (game_id, source)
);

CREATE INDEX IF NOT EXISTS idx_opening_lines_game ON opening_lines(game_id);
```

- `open_spread_home` is home-perspective spread, sign-normalized to match the existing `betting_lines.spread_home_close` convention (negative = home favored) so openers and closers compare directly. (The Kaggle/nflverse sign convention is documented in `ingestion/loader.py`; the probe confirms each source's native sign so the parser flips correctly.)
- `open_ml_home` / `open_ml_away` are American-odds integers, nullable.

---

## Normalized record shape

Both parsers emit the same dataclass so the loader is source-agnostic:

```python
@dataclass(frozen=True)
class OpeningLineRecord:
    season: int
    game_date: str                 # ISO yyyy-mm-dd, parsed to match games.game_date
    home_team: str                 # canonical full name (team_names.canonicalize_team_name)
    away_team: str
    open_spread_home: float | None # home-perspective, negative = home favored
    open_total: float | None
    open_ml_home: int | None       # American odds; None if source lacks ML
    open_ml_away: int | None
    source: str                    # 'sbr' | 'aus'
    source_url: str
```

Team names normalize through the existing `ingestion/team_names.py` (raises on unknown — fail loud, consistent with the real-ML loader).

**Join key:** the loader joins each record to `games` on `(season, home_team, away_team)`, using `game_date` to disambiguate the rare repeat matchup (divisional opponents meet twice a season, once at each home site, so `(season, home, away)` is already unique for regular-season games; playoffs join naturally by date + teams). This sidesteps NFL week numbering entirely — these sources publish dates, not week integers, so there is no playoff-week (100–103) remap to re-derive. The probe confirms each source's date format so the parser can normalize it to `games.game_date`.

---

## Data flow

```
1. (probe, one-time) python scripts/.. or notebook → docs/.../2026-05-29-opening-line-probe.md
   confirms aussportsbetting columns + ML, SBR layout

2. ingestion/opening_line_sbr.py  → fetches SBR HTML (cached to data/raw/), parses → [OpeningLineRecord]   (2007-2021)
   ingestion/opening_line_aus.py  → downloads aussportsbetting xlsx (cached), parses → [OpeningLineRecord] (2013-2024)

3. ingestion/opening_line_loader.py → joins each record to games on (season, home, away)
   (game_date disambiguates repeats), inserts into opening_lines (one row per game per source), logs unmatched

4. scripts/cross_check_openers.py → reads opening_lines + betting_lines,
   computes overlap agreement / closer sanity / coverage / outliers,
   writes docs/.../2026-05-29-opening-line-audit.md
```

Raw downloads cache to `data/raw/` (gitignored) so re-runs don't hammer the sites and so tests can use small saved fixtures rather than the network.

---

## Canonical-opener precedence

`opening_lines` stores **both** sources (no premature dedup) so the audit can compare them. For a single canonical opener per game (which Slice 7 will need), the loader module exposes a small helper with a documented precedence rule:

- **2007–2012:** SBR (only source).
- **2013–2024:** aussportsbetting (still maintained; the only ML source).
- **2013–2021 overlap:** prefer aussportsbetting; SBR retained as the cross-check counterpart.

The precedence rule is final-tunable after the audit: if the audit shows one source is materially cleaner, the helper's rule is adjusted and recorded in the findings note. The helper lives here, but is **not consumed** in this slice (Slice 7 uses it).

---

## The audit (`scripts/cross_check_openers.py`)

Prints to stdout and writes the findings note. Four sections:

1. **Coverage:** games matched per season per source; unmatched counts and reasons (team-name misses, weeks outside a source's range).
2. **Overlap agreement (2013–2021):** for games present in both sources, the share where opening spread and opening total agree within tolerances (±0.5 and ±1.0 pt, matching the Slice 4 cross-check method). Distribution of disagreements; the worst N outliers per market.
3. **Closer sanity:** join openers to `betting_lines` closers; report the correlation of open vs close and the distribution of `close − open` movement per market; flag implausible openers (e.g. `|open − close|` beyond a threshold, or sign disagreement on a heavy favorite).
4. **ML status:** whether opening ML was ingested, coverage if so.

The findings note records all four plus the final precedence decision — structured like `2026-05-28-kaggle-nflverse-crosscheck.md`.

---

## Error handling

- Parsers: a row that fails to parse (the known SBR interleave quirk; a malformed xlsx cell) is **skipped and counted**, not silently dropped — the count surfaces in the loader/audit output. A whole-page/whole-file fetch failure raises with a clear message.
- Unknown team name → `KeyError` from `team_names` (fail loud), consistent with `real_ml_loader`.
- Loader: a record that doesn't join to any `game` is counted as `unmatched` and logged, not inserted.
- Network: scrapers use a normal User-Agent and cache to `data/raw/`; a fetch failure exits non-zero with a hint. Scraping is a manual/one-time step, not part of the test suite.
- All file I/O uses `pathlib` + `utf-8`.

---

## Testing

- **`tests/test_db.py`** — opening_lines table is created, idempotent, enforces the `source` CHECK and FK.
- **`tests/test_opening_line_sbr.py`** — parse a small saved SBR HTML fixture (a few games, including the spread/total interleave and a "pk" pickem); assert correct `OpeningLineRecord`s, correct sign, and that a deliberately malformed row is skipped-and-counted.
- **`tests/test_opening_line_aus.py`** — parse a small saved xlsx fixture; assert spread/total extraction, decimal→American ML conversion (if ML present), and sign normalization.
- **`tests/test_opening_line_loader.py`** — against an in-memory DB seeded with a few `games`: records join correctly, both sources coexist on `(game_id, source)`, unmatched records are counted not inserted, the precedence helper returns the documented source.
- **No network in tests.** The live scrape and the audit run are manual steps; their logic that is unit-testable (parsing, joining, agreement math) is tested via fixtures/synthetic data.
- Full suite stays green; ruff clean.

Target: ~261 baseline + the new tests; exact count finalized in the plan.

---

## Definition of Done

- [ ] Probe note written: aussportsbetting columns + ML verdict, SBR layout + parse strategy
- [ ] `opening_lines` table added to `engine/db.py`; `test_db.py` covers it
- [ ] `ingestion/opening_line_sbr.py` parses SBR HTML → `OpeningLineRecord`s; fixture tests pass
- [ ] `ingestion/opening_line_aus.py` parses aussportsbetting xlsx → `OpeningLineRecord`s; fixture tests pass
- [ ] `ingestion/opening_line_loader.py` joins + loads both sources; precedence helper exists; loader tests pass
- [ ] `scripts/cross_check_openers.py` runs the four-section audit and writes the findings note
- [ ] Opening lines actually loaded into the DB end-to-end (both sources, real data)
- [ ] Findings note written with coverage, overlap agreement, closer sanity, ML status, and the precedence decision
- [ ] `openpyxl` + `lxml` added to `pyproject.toml`; `uv sync` clean
- [ ] `uv run pytest -q` green; `uv run ruff check .` clean
- [ ] README updated with the Slice 6 opening-line workflow
- [ ] `.wolf/memory.md` finding entry; `.wolf/cerebrum.md` decision-log entry

---

## Decisions log (this slice)

- **Decomposition:** CLV split into Slice 6 (ingestion, this) + Slice 7 (analysis). Designing analysis before seeing the data risks rework; the data is unverified.
- **Both sources, full audit:** SBR (2007–2021) + aussportsbetting (2013–2024); the 2013–2021 overlap is cross-validated. Chosen for maximum free coverage and rigor consistent with Slice 5.
- **Markets:** spread + total committed; moneyline is a probe-gated bonus (nullable schema columns either way).
- **Probe-first:** aussportsbetting columns and ML presence are unverified (JS-gated during research); a probe gates the build, like the nflverse probe before Slice 3.
- **Separate `opening_lines` table, `(game_id, source)` key:** keeps both sources for cross-validation; mirrors `real_ml_lines` as its own table.
- **Both sources stored; precedence via a helper, not premature dedup:** preserves audit ability; the canonical-opener rule is documented and tunable after the audit, consumed in Slice 7.
- **Sign-normalize openers to the closer convention:** so open vs close compares directly in the audit and in Slice 7.
- **No network in tests:** scrape/audit are manual one-time runs; testable logic covered by fixtures.
