# Dashboard QOL — Design

- **Date:** 2026-06-13
- **Status:** Approved (brainstorm)
- **Author:** Kolton + Claude

## Goal

Three quality-of-life additions to the deployed dashboard
(https://bestbetodds.streamlit.app/), all in the view layer:

1. A **"last updated" freshness line** on the This Week tab.
2. A **"leans only" toggle** on the Leans tab.
3. A **team filter** on the Leans tab (matching the This Week tab).

## 1. "Odds updated ~X ago" (This Week tab)

The honest freshness signal is *when the odds were pulled*, not when a book last
moved a line (a 5-hour-old snapshot must not read as fresh).

- `ingestion/live_odds.fetch_odds()` writes the pull time to a sidecar
  `data/raw/odds_updated_at.txt` (ISO-8601 UTC) right after it writes the odds
  JSON. The refresh Action (`.github/workflows/refresh-odds.yml`) commits this
  file alongside the odds JSON.
- A pure helper `_humanize_ago(then, now) -> str` renders a relative string:
  "just now" (< 1 min), "~N minutes ago", "~N hours ago", "~N days ago".
- `app/this_week_view.render()` shows a caption `⏱ Odds updated {humanized}`
  below the existing "N games" caption. If the sidecar is missing/unparseable,
  the line is omitted (graceful).
- The file is tracked (it lives in `data/raw/`, which is otherwise tracked; only
  `odds_api_latest.json`-style churn was specifically ignored — this sidecar is
  small and intentionally tracked). After deploy, the Action is run once so the
  timestamp populates accurately; until then the line is simply hidden.

## 2. "Show only games with a lean" toggle (Leans tab)

- `app/tab_leans.render()` adds `st.checkbox("Show only games with a lean")`
  (default off).
- The per-game leans are computed once into rows `[(game, spread_lean, total_lean)]`.
  A pure helper `_has_lean(sp, tot) -> bool` returns `sp.state == "lean" or
  tot.state == "lean"`. When the toggle is on, rows are filtered to those.
- Empty state when the toggle leaves zero games (common and honest):
  "No leans in this slate at the −110 breakeven — every game's a coin flip.
  Uncheck to see all games + best prices."

## 3. Team filter (Leans tab)

- Reuse the This Week pattern exactly: `st.selectbox("Team", ["All teams",
  *board_teams(board)])` + `filter_board(board, team)`. Both helpers already
  exist in `app/this_week_view.py` and are tested; import and reuse them.
- The team filter and the leans-only toggle compose: applying both narrows to the
  selected team's game(s) that also have a lean.

## Architecture / where it lives

- `ingestion/live_odds.py` — `fetch_odds` writes the sidecar timestamp.
- `.github/workflows/refresh-odds.yml` — commit step also adds the sidecar.
- `app/this_week_view.py` — `_humanize_ago` (pure) + a freshness caption in
  `render`.
- `app/tab_leans.py` — team selectbox + leans-only checkbox + `_has_lean` filter;
  reuses `board_teams` / `filter_board`.

No new modules; no engine changes. Everything ships via a push → Streamlit Cloud
auto-redeploy.

## Testing

- `_humanize_ago(then, now)` — pure unit tests: just now, minutes, hours, days
  boundaries.
- `_has_lean` / the leans-only filter — pure unit tests: a row with a lean kept,
  an all-"no_lean" row dropped.
- Team filtering reuses `filter_board` (already covered by
  `tests/test_this_week_view.py`).
- A render smoke test (AppTest) for the Leans tab with the toggle/filter present,
  asserting no exception.

## Out of scope

- No change to the lean logic, the breakeven gate, or any engine math.
- No change to odds frequency or the historical tabs.
- Absolute-time display was considered and declined in favor of the relative
  "~X ago" (timezone-agnostic).
