# NFL Betting Analytics — Slice 7: CLV Engine + Validation

**Date:** 2026-05-30
**Status:** Approved (brainstorming complete)
**Predecessor:** Slice 6 (`docs/superpowers/specs/2026-05-29-nfl-betting-slice6-design.md`)
**Implementation plan:** `docs/superpowers/plans/2026-05-30-nfl-betting-slice7.md` (to be written)
**Successor (planned):** Slice 8 — dashboard (capstone)

---

## Why this slice

The Slice 5 audit concluded that any real edge needs a higher-power signal than static bucket win-rates, and named closing-line value (CLV) as the canonical example — a continuous per-bet quantity measurable with far more statistical power than binary win/loss. Slice 6 ingested the opening lines CLV requires. This slice builds the CLV engine and answers the foundational question before anyone bets on CLV: **in this data, does beating the close actually predict winning?**

## Goal

Compute per-game CLV for spread and total (opener vs closer), then test whether CLV predicts realized results — i.e. whether the closing line is a sharper estimate than the opener. Report it in the honest-metrics framing from Slice 5 (continuous estimates + CI + p-value + power columns; no binary gate).

## Markets (decided)

- **Committed:** spread + total CLV — broad coverage (2007–2024), clean point-based movement.
- **Secondary (stretch):** moneyline CLV — only if the engine generalizes cleanly to the narrower 2020–2024 closing-ML window (`real_ml_lines`). ML does not gate the slice; if it adds meaningful complexity it is deferred to a later slice.

## Out of scope (deferred)

- Any **tradeable** signal-hunting (you cannot know CLV until the line closes; this slice validates signal, it does not build a strategy). A strategy slice follows only if CLV proves informative here.
- Moneyline CLV beyond a clean stretch section.
- The dashboard (Slice 8).
- Intraday line-movement (these sources give open + close only).

---

## What CLV means here (definitions)

For each game we take the **canonical opener** (`ingestion.opening_line_loader.canonical_opener_source(season)` → aussportsbetting for 2013+, SBR for ≤2012) from `opening_lines`, and the **closer** from `betting_lines`, both home-perspective.

**CLV is defined per reference bet, in points, positive when the close moved in the bet's favor (you got a better number than the close):**

- **Spread — reference bet = HOME at the opener:**
  `clv_spread = open_spread_home − close_spread_home`
  (home opens −3, closes −5 → +2: you laid fewer points than the close; the market revised toward home, so home is more likely to cover your smaller opening spread.)

- **Total — reference bet = OVER at the opener:**
  `clv_total = close_total − open_total`
  (total opens 45, closes 47 → +2: you bought the over at a lower bar than the close; the market revised upward, so the over is more likely to cover your opener.)

Both formulas yield **positive = the close agreed with your bet** (informative-movement-in-your-favor). The away side / under side are exact mirrors (−CLV), so we analyze **one reference bet per game** to avoid double-counting the two perfectly anti-correlated sides while still spanning both directions via the sign of CLV.

## The validation test (rigorous core)

For each reference bet we compute two quantities:

1. **CLV** (above) — continuous, signed.
2. **Realized result graded at the OPENING number** — reusing `ingestion.loader.derive_ats_result(home, away, open_spread_home)` for spread and `derive_total_result(home, away, open_total)` for total. The bet wins if it covers the line it actually opened at; pushes are handled exactly as the existing ATS/totals code does (excluded from the win-rate denominator, included in the ROI denominator).

We then test: **does positive CLV predict winning?**

- **Bucketed view:** group bets into CLV buckets (at minimum `negative / zero / positive`; plus finer magnitude bins, e.g. `[−inf,−2), [−2,−0.5), [−0.5,0.5], (0.5,2], (2,inf)`), and for each bucket report n, mean CLV, win rate at the opener, ROI at −110, Wilson CI, p-value vs breakeven, and the Slice 5 power columns (`mde80`, `breakeven_needed`).
- **Continuous view:** the monotonic trend across CLV buckets is the headline — if the close is sharper than the open, win rate should rise monotonically with CLV and cross 52.4% for positive-CLV bets.

**Honesty constraint (stated in output):** this measures whether the close is informative relative to the open. It is **not** a tradeable strategy — CLV is unknown until the close. The report's disclaimer says so explicitly.

---

## Architecture

**Additive. Reuses existing machinery; no restructuring.**

One new module — `engine/clv.py`:
1. Joins `opening_lines` (canonical source per season) → `betting_lines` → `games` via `pandas.read_sql_query`.
2. Applies the opener sanity clamp (below), counting drops.
3. Computes `clv_spread` / `clv_total` and the opener-graded result per game.
4. Assigns each bet to a CLV bucket; aggregates with the existing `engine.bucket_analysis.compute_metrics` (which already produces win rate, ROI, p-value, Wilson CI, by-season, profitable_seasons_pct) and the `engine.stats_utils` power helpers (`mde_winrate_at_power`, `winrate_needed_for_ci`, `roi_from_win_prob`) from Slice 5.
5. Emits a report in the honest-metrics shape (every bucket shown, ranked by mean CLV; point estimate + CI + p-value + power columns; no pass/fail gate) — CLI + `data/processed/clv_report.csv`, mirroring `engine/edge_report.py`'s writer pattern + disclaimer.

| File | Responsibility | Lifecycle |
|---|---|---|
| `engine/clv.py` | CLV computation + bucketing + report (spread & total; ML stretch) | NEW |
| `tests/test_clv.py` | CLV math, opener grading, clamp, bucketing, report shape — fixtures + synthetic | NEW |
| `engine/bucket_analysis.py` | (reuse only — no change expected) | — |
| `engine/stats_utils.py` | (reuse only) | — |
| `README.md` | Slice 7 section + headline finding | MODIFY |
| `docs/superpowers/notes/2026-05-30-clv-findings.md` | The CLV→results finding (written from the real run) | NEW |

If the ML stretch is included, ML CLV computation lives in the same `engine/clv.py` behind a clearly separated function, sourced from `opening_lines.open_ml_*` (aussportsbetting) vs `real_ml_lines` closers, 2020–2024.

---

## Data hygiene — opener sanity clamp

Before computing CLV, drop (and count) implausible opener values so a bad source cell cannot skew results. This was flagged by the Slice 6 review (one corrupted SBR `open_total=541.0`):

- Spread: require `|open_spread_home| ≤ 28` (largest realistic NFL spreads are ~26.5).
- Total: require `25 ≤ open_total ≤ 75`.
- A game failing the clamp on a market is excluded **from that market's** CLV (not the other). Counts are reported in stdout and the findings note.

The same clamp logic is applied to closers as a guard, though `betting_lines` closers are already validated.

---

## Error handling

- A game missing an opener (no `opening_lines` row for the canonical source), a closer, or final scores is excluded from CLV for the affected market and counted — never silently dropped.
- Clamp failures counted per market (above).
- Empty result set (no joinable games) → clear message, exit non-zero (mirrors `engine.validation` / `engine.edge_report`).
- All file I/O uses `pathlib` + `utf-8`.

---

## Testing (TDD)

- **CLV math** — `clv_spread` and `clv_total` formulas with hand-verified signed values, including a line that moved against the bet (negative CLV) and a no-move (zero CLV).
- **Opener grading** — that `derive_ats_result` / `derive_total_result` are called with the OPENING number (not the closing one), with a cover, a loss, and a push case each.
- **Clamp** — an opener outside the band is excluded and counted; the other market for the same game still computes if valid.
- **Bucketing** — a synthetic set of bets lands in the expected CLV buckets; aggregation produces the expected n / win rate / mean CLV.
- **Report shape** — CSV has the honest-metrics columns + disclaimer; every bucket present; ranked by mean CLV; no rows dropped by a gate.
- **End-to-end** — run against the real DB, produce `data/processed/clv_report.csv`, and record the headline (does win rate rise monotonically with CLV; do positive-CLV bets clear breakeven at the opener).
- Full suite stays green; ruff clean. Target ~296 baseline + new tests (exact count in the plan).

---

## Definition of Done

- [ ] `engine/clv.py` computes per-game `clv_spread` / `clv_total` (correct signs) and opener-graded results
- [ ] Opener sanity clamp applied + counted per market
- [ ] CLV bucketing + aggregation reusing `bucket_analysis` + Slice 5 power helpers
- [ ] `data/processed/clv_report.csv` produced in the honest-metrics shape (continuous, no gate) + disclaimer stating "signal test, not a strategy"
- [ ] CLI: `uv run python -m engine.clv` runs end-to-end on the real DB
- [ ] `tests/test_clv.py` covers CLV math, opener grading (incl. pushes), clamp, bucketing, report shape
- [ ] Headline recorded: does win rate rise monotonically with CLV; do positive-CLV bets beat 52.4% at the opener
- [ ] (Stretch) ML CLV section if it generalized cleanly; otherwise explicitly deferred in the findings note
- [ ] `docs/superpowers/notes/2026-05-30-clv-findings.md` written from the real run
- [ ] `README.md` Slice 7 section + headline; Scope bullet added
- [ ] `uv run pytest -q` green; `uv run ruff check .` clean
- [ ] `.wolf/memory.md` finding entry; `.wolf/cerebrum.md` decision-log entry

---

## Decisions log (this slice)

- **Validate before strategize:** the slice tests whether CLV predicts results (is the close sharper than the open) before any tradeable signal work. If the link is weak, that is itself the finding.
- **One reference bet per game (home / over at the opener):** avoids double-counting the two mirror-image sides; the sign of CLV spans both directions.
- **Grade at the OPENING number:** the bet's realized result must be evaluated at the price actually taken (the opener), not the close — that is what links CLV to profit.
- **CLV signs:** `clv_spread = open_spread_home − close_spread_home`; `clv_total = close_total − open_total`. Both positive = the close moved in the bet's favor. Documented and unit-pinned because the spread (signed, negative=favored) and total (magnitude) conventions differ.
- **Honest-metrics framing reused:** continuous estimates + power columns from Slice 5; no binary credibility gate.
- **Opener clamp:** carried from the Slice 6 review (the 541.0 SBR cell); per-market exclusion, counted.
- **Canonical opener + Kaggle closer pairing:** `canonical_opener_source` for the opener, `betting_lines` for the closer — the Slice 6 audit confirmed this pairing's closer-sanity is healthy.
- **ML is secondary:** spread/total is the clean, broad core; ML CLV is gated on clean generalization to 2020–2024.
