# NFL Betting Analytics — Slice 9: Historical Showcase Tabs

**Date:** 2026-05-31
**Status:** Approved (brainstorming complete)
**Predecessor:** Slice 8 (`docs/superpowers/specs/2026-05-30-nfl-betting-slice8-design.md`)

---

## Why this slice

Slice 8 shipped the live "This Week" board as the first tab of the Streamlit app. This slice adds the **historical showcase tabs** that tell the project's story — turning the app from a single live tool into the full capstone the project has been building toward (the "make it great" dashboard). It surfaces work already done (Slices 5–7): the honest edge report, the CLV finding, and the opening-line audit. No new analysis beyond one small re-grading helper.

## Goal

Add four tabs to the existing app — **The Finding · Edge Report · CLV Explorer · Data & Audit** — in refined-dark, reading the already-produced artifacts and the tested engine functions, with the honest framing carried throughout.

## Tab order (decided)

`This Week · The Finding · Edge Report · CLV Explorer · Data & Audit` — the live tool leads (daily use); the showcase tabs sit behind it.

## Out of scope (deferred)

- Any new analysis beyond the `grade_at='close'` re-grading helper (below).
- Moneyline CLV in the explorer (spread + total only — derived ML buckets are biased).
- Deployment/hosting (local `streamlit run`); auth; bet tracking.

---

## Architecture

**Additive — extends the existing `app/` package; no engine refactor.** The audit confirmed every analysis function already returns structured data; the tabs are thin views over `app/data.py` (a cached data-access layer). Charts use Altair (already a dep from Slice 8).

| File | Responsibility | Lifecycle |
|---|---|---|
| `engine/clv.py` | Add `grade_at: str = "open"` param to `build_bets_from_db` (grade the same bets at the opener OR the closer) — for the open-vs-close proof panel | MODIFY |
| `tests/test_clv.py` | Test `grade_at="close"` regrades at the closing line | MODIFY |
| `app/data.py` | Cached data-access layer: edge report, CLV ladders (open & close, filterable by market/season), opening-line coverage, audit summary | NEW |
| `tests/test_app_data.py` | Unit tests for the data-access helpers | NEW |
| `app/tab_finding.py` | "The Finding" render (hero) | NEW |
| `app/tab_edge.py` | "Edge Report" render | NEW |
| `app/tab_clv.py` | "CLV Explorer" render (interactive) | NEW |
| `app/tab_data.py` | "Data & Audit" render | NEW |
| `app/charts.py` | Shared Altair chart builders (refined-dark themed): CLV ladder, CI error-bar chart | NEW |
| `app/main.py` | Wire the 5 tabs in order; sidebar season-range control | MODIFY |
| `tests/test_app_smoke.py` | Extend the AppTest smoke test to boot all 5 tabs | MODIFY |
| `README.md` | Slice 9 section | MODIFY |

Files are split one-render-per-tab to stay focused and independently testable.

---

## The `grade_at` engine addition (the one new piece)

`engine.clv.build_bets_from_db(conn)` currently grades each reference bet at the OPENING number. Add `grade_at: str = "open"`:
- `grade_at="open"` (default, unchanged): grade with `open_spread_home` / `open_total`.
- `grade_at="close"`: grade with `spread_home_close` / `total_close`.
The CLV value is identical either way (always open vs close); only which line the bet is *graded against* changes. Feeding both through the existing `aggregate_clv` yields the two ladders the proof panel contrasts: graded@open rises monotonically with CLV; graded@close is flat (the signal has been absorbed by the close). This makes permanent the re-grading the Slice-5-arc audit did by hand to prove the finding is genuine.

---

## The four tabs

### The Finding (narrative hero — static)
- Headline + one-line plain-English summary (the close is sharper than the open).
- Three stat cards: the 39.9% → 57.6% spread win-rate swing; the CLV↔result correlation (r≈0.12, p≈1e-14); total bets analyzed (~9,139, from the CLV report).
- The **CLV win-rate ladder** (spread + total) as an Altair bar chart from the `grade_at="open"` ladder.
- The **open-vs-close proof panel**: two small ladders side by side — graded@open (rises) vs graded@close (flat) — the artifact-killer made visual.
- Honesty footer: signal test, not a strategy + disclaimer.

### Edge Report (read `data/processed/edge_report.csv`)
- The honest-metrics table: every bucket with `point_roi, ci_low, ci_high, p_value, mde80_roi, breakeven_needed_roi`.
- An Altair chart: per-bucket point ROI with **95% CI error bars** (visibly straddling zero) and a breakeven reference line.
- Market filter (ats / totals / ml).
- Framing: "no certified static edge — a power limit, not proof of efficiency."

### CLV Explorer (interactive — from the DB)
- Market selector (spread / total) + season-range slider that re-bucket live via `build_bets_from_db(grade_at="open")` filtered to the season range, then `aggregate_clv`.
- The CLV ladder (Altair) + the bucket table (n, mean_clv, win_rate, roi, CI, p_value, mde80).
- Honest caveat: positive-CLV tail buckets are statistically marginal; the monotonic shape is the evidence.

### Data & Audit (trust tab)
- Opening-line coverage per source per season (queried from `opening_lines` joined to `games`).
- Cross-source agreement headline (spread ~75% / total ~82% within 1pt, 2013–2021 overlap) and closer-sanity, sourced from the audit findings.
- Data-provenance panel: the four sources (Kaggle closing 2004–2024, nflverse real ML 2020–2024, SBR openers 2007–2021, aussportsbetting openers 2006–2024) with what each provides.

---

## `app/data.py` (cached data-access layer)

Pure-ish, `@st.cache_data`-wrapped loaders — where the testable logic lives:
- `load_edge_report() -> pandas.DataFrame` (reads edge_report.csv, strips `#` comment lines).
- `clv_ladder(grade_at, market, season_range) -> pandas.DataFrame` (build_bets_from_db + season filter + aggregate_clv → per-bucket rows for the chosen market).
- `opening_line_coverage() -> pandas.DataFrame` (per source/season counts from the DB).
- `audit_summary() -> dict` (the cross-source agreement / provenance facts — small static constants matching the audit note, with a comment pointing to `docs/superpowers/notes/2026-05-29-opening-line-audit.md` as the source of truth).
Each loader returns an empty/None-friendly result and the tab shows a "run X to generate this" message if the artifact/DB is missing.

The season filter on CLV: `build_bets_from_db` returns bets with a `season` field, so the explorer filters the bet list by `season_range` before `aggregate_clv` — no new query needed.

---

## Error handling

- Missing `edge_report.csv` / `clv_report.csv` / DB → the affected tab shows a friendly "generate this with `…`" message; other tabs still render.
- Empty CLV result for a season filter → "no games in range" message, not a crash.
- All artifact reads strip leading `#` comment lines (reuse the existing pattern).

---

## Testing

- **`tests/test_clv.py`** — `grade_at="close"` grades at the closing line (a bet that covers the open but not the close flips result); default stays `"open"`.
- **`tests/test_app_data.py`** — `load_edge_report` parses the CSV (skips comments); `clv_ladder` filters by market + season range and returns expected bucket rows; `clv_ladder(grade_at="close")` differs from `"open"`; missing-file paths return empty, not raise.
- **`tests/test_app_smoke.py`** — extend AppTest: the app boots with all 5 tabs and no exception (no live network, empty-data-friendly).
- **designqc** — after wiring, screenshot each tab on real data and polish (the "make it great" pass).
- Full suite stays green; ruff clean.

---

## Definition of Done

- [ ] `build_bets_from_db(grade_at=...)` added; `grade_at="close"` tested; default unchanged
- [ ] `app/data.py` loaders + `tests/test_app_data.py` green
- [ ] `app/charts.py` Altair builders (ladder, CI error bars), refined-dark
- [ ] Four tab renders (`tab_finding`, `tab_edge`, `tab_clv`, `tab_data`)
- [ ] `app/main.py` wires 5 tabs in order (This Week first) + sidebar season-range
- [ ] AppTest smoke boots all 5 tabs; full suite green; ruff clean
- [ ] designqc pass on each tab (real data) with polish applied
- [ ] README Slice 9 section; Scope bullet
- [ ] `.wolf/memory.md` + `.wolf/cerebrum.md` entries

---

## Decisions log (this slice)

- **This Week leads** — the live tool is daily-use; showcase tabs sit behind it.
- **One new engine piece only** — `grade_at='close'` for the proof panel; everything else reads existing artifacts.
- **Thin views over a cached `app/data.py`** — testable data prep, minimal UI logic; one module per tab.
- **Altair for charts** (already a dep); refined-dark carried over.
- **Honest framing preserved** — edge report "power limit not efficiency"; CLV "signal test, not a strategy"; tail buckets flagged marginal.
- **All four tabs in one slice** — cohesive showcase; each tab is independently testable.
