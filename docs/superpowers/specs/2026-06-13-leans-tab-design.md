# Leans Tab — Design

- **Date:** 2026-06-13
- **Status:** Approved (brainstorm) — updated for dynamic season filtering — pending spec review
- **Author:** Kolton + Claude

## Goal

Add a new dashboard tab that distills each upcoming game on the This Week board
into a plain-English, per-market read so the user does not have to read the
bucket tables. For each game it shows a **spread read** and a **total read**,
each combining (a) the historical directional lean and (b) the best available
price for the relevant side.

**The leans are dynamic over the season-range slider:** the historical rates
backing every lean are recomputed from only the seasons the user selects, so
narrowing to (e.g.) 2018–2024 re-evaluates every game against that window.

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
- **Dynamic recompute over the season-range slider** (the slider already exists;
  it will now drive this tab as well as the CLV Explorer).

**Out of scope**
- Moneyline leans.
- Any predictive model or "this will win" language.
- Parlays, staking, bankroll, or bet-sizing advice.
- Changing the existing This Week board or the historical CSVs.

## Architecture

Follow the established pattern (pure engine logic + thin Streamlit view, like
`engine/this_week.py` → `app/this_week_view.py`, and the CLV-Explorer live-recompute
pattern in `app/data.py`):

- **`engine/ats.py` / `engine/totals.py`** (modify) — add an optional
  `season_range: tuple[int, int] | None = None` parameter to
  `ats_by_spread_bucket` and `totals_by_line_bucket`. When given, the SQL filters
  `g.season BETWEEN lo AND hi` (bound params). Default `None` = all seasons, so
  the existing full-history CSV generation is unchanged.
- **`engine/leans.py`** (new, pure, no Streamlit) — the decision rule. Takes a
  `ThisWeekGame` and a **rates map** (`{bucket_name: {"win_rate", "n"}}`) for the
  selected seasons, buckets the game's consensus line itself, and returns a
  `MarketLean`. Fully unit-testable by passing a small dict.
- **`app/data.py`** (modify) — `spread_bucket_rates(season_range)` and
  `total_bucket_rates(season_range)`: cached (`st.cache_data`, keyed by the range)
  wrappers that call the season-filtered engine functions and reshape the result
  into the rates map.
- **`app/tab_leans.py`** (new, thin) — `render(board, spread_rates, total_rates)`
  with the honesty banner and per-game cards.
- **`app/main.py`** (modify) — build the board once, compute the two rates maps
  from the current slider value, pass them to the new tab. Relabel the slider
  (it now drives Leans + CLV Explorer).

Per-game live inputs already live on `ThisWeekGame`:
`cons_spread_home`, `cons_total`, `best_spread_home/away`,
`best_total_over/under`. The historical rate is no longer read from the static
`spread_ctx`/`total_ctx` fields (those still serve the This Week board); the
Leans tab supplies a season-filtered rates map instead.

## The lean logic (`engine/leans.py`)

Breakeven constant: `engine.stats_utils.BREAKEVEN_AT_NEG_110` (≈ 0.5238).
Sample floor: `engine.bucket_analysis.INSUFFICIENT_SAMPLE_THRESHOLD` (50).
Bucketing: `engine.ats.bucket_spread`, `engine.totals.bucket_total`.

A **rates map** is `{bucket_name: {"win_rate": float, "n": int}}`, where for
spread `win_rate` is the home cover rate and for total `win_rate` is the over
rate, computed over the selected seasons. Buckets with `n == 0` (no games in the
window) are treated as no data.

### Spread read

- `bucket = bucket_spread(cons_spread_home)`. Look it up in the spread rates map.
- If the consensus spread is missing → `no_line`. If the bucket is absent or has
  `n == 0` → `no_data`.
- home rate = `win_rate`; away rate ≈ `1 − win_rate` (small-pushes approximation;
  the map stores only the home cover rate — pushes are a low single-digit %).
- A side is the lean iff its rate `≥ breakeven` **and** `n ≥ 50` **and** the
  bucket is not `pickem`. At most one side can clear breakeven.
- Human label from the consensus spread + leaned side, e.g. home `-6.5` and home
  clears → `"Los Angeles Rams -6.5 · home favorite"`; a home dog (`+6.5`) whose
  away side clears → `"Seattle Seahawks -6.5 · away favorite"`.

### Total read

- `bucket = bucket_total(cons_total)`. Over rate = `win_rate`; under ≈
  `1 − win_rate`. Over leans iff over rate clears breakeven (n≥50); under iff its
  rate does. Label `"OVER 44.5"` / `"UNDER 44.5"` from `cons_total`.

### Best price

- Spread lean home → `best_spread_home`; away → `best_spread_away`. Total over →
  `best_total_over`; under → `best_total_under`. On **no lean**, show both sides
  for shopping. `BestLine` renders via the existing `_fmt_best`.

### Data model

```python
@dataclass(frozen=True)
class MarketLean:
    market: str                 # "spread" | "total"
    state: str                  # "lean" | "no_lean" | "no_data" | "no_line"
    side_label: str | None      # "Seattle Seahawks -6.5 · away favorite", "UNDER 44.5", or None
    rate: float | None          # leaned side's rate when state=="lean"; else the
                                # reference-side rate (home for spread, over for total)
    n: int | None
    best_for_lean: BestLine | None      # price for the leaned side (state == "lean")
    best_primary: BestLine | None       # home / over  — for shopping on no_lean
    best_secondary: BestLine | None     # away / under
```

`spread_lean(game, spread_rates)`, `total_lean(game, total_rates)`,
`game_leans(game, spread_rates, total_rates)`.

## Rendering

- **Top banner** reuses the honesty language: historical context + best price,
  not certified picks; "no lean" means the history is a coin flip at −110.
- **Per game** (one card), two labelled rows — Spread and Total:
  - `lean`: `LEAN: <side_label> — <rate> historically (n=N), clears the -110
    breakeven; context, not a pick` + `→ Best price: <best_for_lean>`.
  - `no_lean`: `No lean — coin flip (<rate>, n=<n>)`, where `<rate>` is the
    reference-side rate (home cover for spread, over for total) + both best lines.
  - `no_data`: `No historical data for this bucket` (+ best lines if any). Common
    on short season windows.
  - `no_line`: that market's row is skipped for the game.
- A caption notes the tab reflects the selected season range and that narrowing
  it shrinks samples (more "no lean").
- Game order reuses the board's existing order (biggest spread mover first).

Example (full-history window):

```
SEAHAWKS at RAMS — Sun 4:25 PM
  Spread   LEAN: Rams -6.5 · home favorite — 53.1% historically (n=612),
           clears the -110 breakeven; context, not a pick
           → Best price: -6.5 (-105) at FanDuel
  Total    No lean — coin flip (49.8%, n=540)
           → best over 44.5 (-108) DraftKings · best under 44.5 (-105) BetMGM
```

## Dynamic season filtering

- The sidebar slider (currently labeled "Season range (CLV Explorer)") is
  relabeled and its value is passed to both the CLV Explorer and the Leans tab.
- `spread_bucket_rates(season_range)` / `total_bucket_rates(season_range)`
  recompute the per-bucket rates over only those seasons (cached per range).
- **Consequence (intended):** narrowing the window shrinks `n` fast, so more
  buckets fall under the `n ≥ 50` floor and flip to "no lean." The tab gets
  quieter, not just different, on short windows — this is the honesty gate doing
  its job, and is surfaced in the caption.
- The games being leaned are the upcoming slate; the slider filters the
  *historical seasons* that inform each lean (the DB's completed seasons,
  ~2004–2024), not the games shown.

## Edge cases

- No live odds pulled / empty board → same empty-state the This Week tab shows.
- Missing consensus line for a market (`cons_* is None`) → that market's row is
  `no_line`; the other market still renders.
- Bucket absent from the rates map or `n == 0` in the window → `no_data`.
- DB missing / unreadable → `*_bucket_rates` returns `{}` → every read is
  `no_data`; best prices still render.
- `best_*` is `None` for a side → `—` (existing `_fmt_best` convention).

## Testing

- **Engine season filter** (`tests/test_ats.py`, `tests/test_totals.py`): build an
  in-memory DB via `init_schema`, insert two games in the same bucket but
  different seasons, assert the unfiltered call counts both and a season-range
  call counts one.
- **`engine/leans.py`** (`tests/test_leans.py`), passing a small rates map:
  spread home lean; spread away lean; total over/under lean; below-breakeven
  (0.515) → no_lean (the key honesty rule); n=49 vs 50 gate; `pickem` → no_lean;
  bucket absent / `n == 0` → no_data; `cons_* is None` → no_line; best-line
  selection matches the leaned side.
- **`app/data.py`** (`tests/test_app_data.py`): `spread_bucket_rates` /
  `total_bucket_rates` return a dict keyed by bucket with `win_rate`/`n`, and a
  narrow season range yields ≤ the full-range `n` for a populated bucket (use the
  in-memory DB pattern or monkeypatch `_open_db`).
- **`app/tab_leans.py`** (`tests/test_leans_view.py`): pure `_lean_headline`
  substring tests + a render smoke test (AppTest) over a board with lean,
  no_lean, and no_data/no_line games.

## Assumptions / decisions

- **Breakeven anchor at 52.38%, not 50%** (approved). Most games show "no lean,"
  especially on short windows. Intended.
- **Dynamic over the season slider** (approved). Slider drives Leans + CLV
  Explorer; relabel accordingly.
- Away/under rates derived as `1 − home/over rate` (small-pushes approximation).
- The `n ≥ 50` gate uses the bucket's total sample `n` (push-inclusive, matching
  the displayed number); pushes are a low single-digit % so this tracks the
  decided-count threshold closely.
- Historical rates are measured at uniform −110; a found best price can only
  improve the real breakeven, so a lean clearing −110 historically is a
  conservative bar.
