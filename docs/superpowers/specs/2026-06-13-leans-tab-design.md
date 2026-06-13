# Leans Tab — Design

- **Date:** 2026-06-13
- **Status:** Approved (brainstorm) — pending spec review
- **Author:** Kolton + Claude

## Goal

Add a new dashboard tab that distills each upcoming game on the This Week board
into a plain-English, per-market read so the user does not have to read the
bucket tables. For each game it shows a **spread read** and a **total read**,
each combining (a) the historical directional lean and (b) the best available
price for the relevant side.

## The honesty constraint (why this is a "lean," not a "pick")

The project's headline finding is that the static historical buckets are
**noise** for prediction — "home dogs of 3–7 covered 53% over 14 seasons" does
not mean the home dog is a good bet in *this* game. The only validated signal
(CLV) is unknowable until the line closes, so it cannot drive a pre-game pick.

Therefore this feature must never present a base rate as a prediction. It is a
**context + best-price** readout. Two rules enforce this:

1. A side is only named as a lean when its historical rate **clears the −110
   breakeven (52.38%)** *and* the sample is adequate (`n ≥ 50`). A 51% side is a
   *losing* bet at −110 and must not be surfaced as a lean.
2. When no side clears that bar, the card says **"no lean — coin flip"** and
   still shows the best price for both sides (line shopping always applies and is
   the project's one genuinely repeatable edge). "No lean" is a real answer, not
   a gap.

No moneyline lean (the historical ML data is derived/biased and is already
excluded from board context). No profit claims, no model, no parlays.

## Scope

**In scope**
- A new `Leans` tab in the Streamlit app.
- Per game: a spread read and a total read.
- Each read: directional lean (or "no lean"), the historical rate + `n`, a
  breakeven-clearing tag, the plain-English exert, and best price(s).

**Out of scope**
- Moneyline leans.
- Any predictive model or "this will win" language.
- Parlays, staking, bankroll, or bet-sizing advice.
- Changing the existing This Week board, the historical CSVs, or the engines that
  produce them.

## Architecture

Follow the established pattern (pure engine module + thin Streamlit view, e.g.
`engine/this_week.py` → `app/this_week_view.py`):

- **`engine/leans.py`** (new, pure, no Streamlit) — turns a `ThisWeekGame` into a
  spread `MarketLean` and a total `MarketLean`. Fully unit-testable.
- **`app/tab_leans.py`** (new, thin) — renders the leans for the current board
  with the honesty banner and per-game cards.
- **`app/main.py`** — wire in the new tab. The board data source is the same one
  the This Week tab already builds (live `GameOdds` + stored openers →
  `engine.this_week.build_board`); no new data plumbing.

All inputs already live on `ThisWeekGame`:
`cons_spread_home`, `cons_total`, `best_spread_home/away`,
`best_total_over/under`, `spread_ctx`, `total_ctx`
(where each `*_ctx` is `{bucket, win_rate, n}` or `None`).

## The lean logic

Breakeven constant: reuse `engine.stats_utils.BREAKEVEN_AT_NEG_110` (≈ 0.5238).
Sample floor: reuse `engine.bucket_analysis.INSUFFICIENT_SAMPLE_THRESHOLD` (50).

### Spread read

- `spread_ctx['win_rate']` is the **home** cover rate for the game's spread
  bucket; `spread_ctx['n']` is the sample. The bucket name
  (`home_fav_*` / `home_dog_* / pickem`) tells us whether home is the favorite or
  dog and the point range.
- Evaluate both sides:
  - home rate = `win_rate`
  - away rate ≈ `1 − win_rate` (a small-pushes approximation; the CSV only stores
    the home cover rate — documented as an approximation, acceptable because
    pushes are a low single-digit %).
- A side is the lean iff its rate `≥ BREAKEVEN_AT_NEG_110` **and** `n ≥ 50`.
  (At most one side can clear breakeven; if neither does → no lean.)
- Human label is built from the consensus spread and the leaned side, e.g.
  home is `-6.5` and home leans → `"Seattle -6.5 · home favorite"`; away leans on
  a `+6.5` home dog → `"Rams +6.5 · away favorite"`.
- `pickem` buckets are treated as no-lean by nature (no favorite/dog edge).

### Total read

- `total_ctx['win_rate']` is the **over** hit rate for the game's total bucket;
  under rate ≈ `1 − win_rate`.
- Over is the lean iff over rate `≥ breakeven` and `n ≥ 50`; under iff its rate
  clears the bar. Otherwise no lean.
- Label: `"OVER 44.5"` / `"UNDER 44.5"` using `cons_total`.

### Best price selection

- Spread lean home → `best_spread_home`; away → `best_spread_away`.
- Total lean over → `best_total_over`; under → `best_total_under`.
- On **no lean**, show both sides' best lines so shopping is still useful.
- A `BestLine` renders as `point (price) at book` (reuse the existing
  `_fmt_best`-style formatting from `this_week_view`).

### Data model (illustrative)

```python
@dataclass(frozen=True)
class MarketLean:
    market: str                 # "spread" | "total"
    state: str                  # "lean" | "no_lean" | "no_data" | "no_line"
    side_label: str | None      # "Rams +6.5 · away favorite", "UNDER 44.5", or None
    rate: float | None          # leaned side's rate when state=="lean"; otherwise the
                                # reference-side rate (home for spread, over for total)
    n: int | None
    best_for_lean: BestLine | None      # price for the leaned side (state == "lean")
    best_primary: BestLine | None       # home / over  — for shopping on no_lean
    best_secondary: BestLine | None     # away / under
```

The view turns `state` + fields into the displayed lines. Exact field names are
finalized in the implementation plan.

## Rendering

- **Top banner** reuses the existing honesty language: historical context + best
  price, not certified picks; "no lean" means the history is a coin flip at −110.
- **Per game** (one card), two labelled rows — Spread and Total:
  - `state == "lean"`: `LEAN: <side_label>` + one line of plain English
    (`"Home favorites of 3–7 covered 53.1% over N seasons (n=612), clears the
    -110 breakeven. Historical context, not a certified pick."`) + `→ Best price:
    <best_for_lean>`.
  - `state == "no_lean"`: `No lean — coin flip (<rate>, n=<n>)`, where `<rate>` is
    the reference-side rate (home cover for spread, over for total) so the number
    is unambiguous + both best lines for shopping.
  - `state == "no_data"`: `No historical data for this bucket.` + best lines if
    any.
  - `state == "no_line"`: market skipped (no consensus line posted yet).
- Game order: reuse the board's existing order (biggest spread mover first) — it
  is descriptive, not an edge ranking, consistent with the board.

Example:

```
SEAHAWKS at RAMS — Sun 4:25 PM
  Spread   LEAN: Rams -6.5 · home favorite
           Home favorites of 3–7 covered 53.1% over 14 seasons (n=612),
           clears the -110 breakeven. Historical context, not a certified pick.
           → Best price: -6.5 (-105) at FanDuel
  Total    No lean — coin flip (49.8% over, n=540)
           → Best over 44.5 (-108) DraftKings · best under 44.5 (-105) BetMGM
```

## Edge cases

- No live odds pulled / empty board → same empty-state the This Week tab shows.
- Missing consensus line for a market (`cons_* is None`) → that market's row is
  `no_line` (skipped) for that game; the other market still renders.
- `*_ctx is None` (no CSV or no bucket match) → `no_data`, best lines still shown.
- `best_*` is `None` for a side → render `—` for that price (existing convention).
- Historical CSVs absent (`ats_by_bucket.csv` / `totals_by_bucket.csv` not
  generated) → every read is `no_data`; the tab still renders best prices and a
  hint to generate the reports.

## Testing

Unit tests against the pure `engine/leans.py` (no Streamlit), using synthetic
`ThisWeekGame` instances:

- Spread lean home (home rate above breakeven, n≥50) → `state=="lean"`, correct
  side label and best line.
- Spread lean away (home rate low so away clears breakeven) → away lean.
- Total over lean / under lean.
- Below-breakeven but >50% (e.g. 0.515) → `no_lean` (the breakeven anchor, the
  key honesty rule).
- Sample gate: n=49 → `no_lean`/suppressed even if rate clears breakeven; n=50 →
  allowed.
- `pickem` spread bucket → `no_lean`.
- `*_ctx is None` → `no_data`; `cons_* is None` → `no_line`.
- Best-line selection matches the leaned side.

A light smoke test that `app/tab_leans.render` runs without raising on a board
containing a lean game, a no-lean game, and a no-data game (mirroring the
`this_week_view` render test).

## Assumptions / decisions

- **Breakeven anchor at 52.38%, not 50%** (approved). Consequence: most games
  show "no lean." This is intended — it keeps the feature honest and flags when
  *not* to bet.
- Away/under rates are derived as `1 − home/over rate` (small-pushes
  approximation) because the CSVs store only the home/over rate.
- Historical rates are measured at uniform −110; the best-price shown can only
  improve the real breakeven, so a lean that clears −110 historically is a
  conservative bar.
