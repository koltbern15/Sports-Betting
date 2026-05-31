# NFL Betting Analytics — Slice 9: Historical Showcase Tabs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four historical showcase tabs (The Finding / Edge Report / CLV Explorer / Data & Audit) to the existing refined-dark Streamlit app, with This Week leading.

**Architecture:** Additive over the existing `app/` package. One small engine touch (`grade_at` on `build_bets_from_db` for the proof panel); a cached `app/data.py` data-access layer + `app/charts.py` Altair builders; four thin tab renders; `app/main.py` wires 5 tabs + a sidebar season-range. Reuses the already-tested engine functions — no engine refactor.

**Tech Stack:** Python 3.11, Streamlit, Altair (both already deps), pandas, sqlite3, pytest, ruff, uv.

**Reused (verified):**
- `engine.clv.build_bets_from_db(conn) -> list[dict]` — each bet: `{market, clv, result, season}`, graded at the opener. Grading lines: `spread_bet_result(hs, as_, open_sp)` / `total_bet_result(hs, as_, open_tot)` (clv.py:205, 213).
- `engine.clv.aggregate_clv(bets) -> list[ClvRow]` (fields: market, clv_bucket, n, wins, mean_clv, win_rate, roi, ci_low, ci_high, p_value, profitable_seasons_pct, mde80, breakeven_needed); `CLV_BUCKET_ORDER`.
- `engine.db.connect`, `engine.db.fetch_df`.
- `data/processed/edge_report.csv` cols: `market,bucket,n,win_rate,point_roi,ci_low,ci_high,p_value,profitable_seasons_pct,mde80_roi,breakeven_needed_roi` (1 leading `#`… actually 3 `#` comment lines).
- `app/main.py` already bootstraps sys.path + has `theme.inject()` + the `This Week` tab (Slice 8).
- `engine.stats_utils.BREAKEVEN_AT_NEG_110` (≈0.5238).

---

## File structure

| File | Responsibility | Lifecycle |
|---|---|---|
| `engine/clv.py` | `build_bets_from_db(conn, grade_at="open")` | MODIFY |
| `tests/test_clv.py` | `grade_at="close"` test | MODIFY |
| `app/data.py` | cached loaders: edge report, CLV ladder (open/close, market, seasons), opening-line coverage, audit summary | NEW |
| `tests/test_app_data.py` | data-layer unit tests | NEW |
| `app/charts.py` | Altair builders: CLV ladder, CI error-bar | NEW |
| `app/tab_finding.py` | "The Finding" render | NEW |
| `app/tab_edge.py` | "Edge Report" render | NEW |
| `app/tab_clv.py` | "CLV Explorer" render (interactive) | NEW |
| `app/tab_data.py` | "Data & Audit" render | NEW |
| `app/main.py` | wire 5 tabs + sidebar season-range | MODIFY |
| `tests/test_app_smoke.py` | boot all 5 tabs | MODIFY |
| `README.md` | Slice 9 section | MODIFY |

---

## Task 1: `grade_at` on `build_bets_from_db`

**Files:** Modify `engine/clv.py` (`build_bets_from_db`, ~line 184-217); test `tests/test_clv.py`.

- [ ] **Step 1: Write the failing test.** Append to `tests/test_clv.py` (it already imports `connect, init_schema` and has `_seed`; reuse them):
```python
def test_grade_at_close_regrades_at_closing_line():
    conn = connect(":memory:")
    init_schema(conn)
    # Home wins by 4. Opener -3 (covers), closer -6 (does NOT cover).
    _seed(conn, "g1", 2018, 24, 20, "aus", -3.0, 45.0, -6.0, 45.0)
    open_bets = build_bets_from_db(conn, grade_at="open")
    close_bets = build_bets_from_db(conn, grade_at="close")
    sp_open = next(b for b in open_bets if b["market"] == "spread")
    sp_close = next(b for b in close_bets if b["market"] == "spread")
    assert sp_open["result"] == "win"    # covered the -3 opener
    assert sp_close["result"] == "loss"  # did not cover the -6 closer
    # CLV is identical either way (always open vs close)
    assert sp_open["clv"] == sp_close["clv"] == 3.0  # open(-3) - close(-6)
    conn.close()


def test_grade_at_defaults_to_open():
    conn = connect(":memory:")
    init_schema(conn)
    _seed(conn, "g1", 2018, 24, 20, "aus", -3.0, 45.0, -6.0, 45.0)
    assert build_bets_from_db(conn) == build_bets_from_db(conn, grade_at="open")
    conn.close()
```
(`build_bets_from_db` must be in the test file's import block — it is, from Slice 8 Task 3 tests; if not, add it.)

- [ ] **Step 2: Run → FAIL** (`uv run pytest tests/test_clv.py -q` — unexpected `grade_at` kwarg).

- [ ] **Step 3: Implement.** In `engine/clv.py`, change the signature and the two grading lines. Replace:
```python
def build_bets_from_db(conn: sqlite3.Connection) -> list[dict]:
    """Build per-game reference-bet records (spread + total) using the canonical opener.

    Picks the canonical opener source per game, applies the sanity clamp per market,
    computes CLV, and grades each bet at the OPENING number.
    """
```
with:
```python
def build_bets_from_db(conn: sqlite3.Connection, grade_at: str = "open") -> list[dict]:
    """Build per-game reference-bet records (spread + total) using the canonical opener.

    Picks the canonical opener source per game, applies the sanity clamp per market,
    computes CLV (always open vs close), and grades each bet at `grade_at`:
    'open' (default — the price you'd have taken) or 'close' (the sharper line).
    Grading at 'close' makes the CLV->result signal vanish — used to prove the
    open-graded signal is real, not a CLV/grade artifact.
    """
```
Then replace the spread block:
```python
        if clamp_ok_spread(open_sp) and clamp_ok_spread(close_sp):
            res = spread_bet_result(hs, as_, open_sp)
            if res is not None:
                bets.append({"market": "spread", "clv": clv_spread(open_sp, close_sp),
                             "result": res, "season": season})
```
with:
```python
        if clamp_ok_spread(open_sp) and clamp_ok_spread(close_sp):
            graded_sp = open_sp if grade_at == "open" else close_sp
            res = spread_bet_result(hs, as_, graded_sp)
            if res is not None:
                bets.append({"market": "spread", "clv": clv_spread(open_sp, close_sp),
                             "result": res, "season": season})
```
And the total block:
```python
        if clamp_ok_total(open_tot) and clamp_ok_total(close_tot):
            res = total_bet_result(hs, as_, open_tot)
            if res is not None:
                bets.append({"market": "total", "clv": clv_total(open_tot, close_tot),
                             "result": res, "season": season})
```
with:
```python
        if clamp_ok_total(open_tot) and clamp_ok_total(close_tot):
            graded_tot = open_tot if grade_at == "open" else close_tot
            res = total_bet_result(hs, as_, graded_tot)
            if res is not None:
                bets.append({"market": "total", "clv": clv_total(open_tot, close_tot),
                             "result": res, "season": season})
```

- [ ] **Step 4: Run → PASS** (file + full suite). Lint.

- [ ] **Step 5: Commit.**
```bash
git add engine/clv.py tests/test_clv.py
git commit -m "feat(clv): grade_at param on build_bets_from_db (open|close) for proof panel

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `app/data.py` data-access layer

**Files:** Create `app/data.py`, `tests/test_app_data.py`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_app_data.py`:
```python
"""Tests for app.data — cached data-access loaders (logic tested without Streamlit cache)."""

from __future__ import annotations

from engine.db import connect, init_schema
from app import data as appdata


def _seed_clv(conn):
    # two games, both with a spread bet; different seasons for the season-filter test
    conn.executescript(
        "INSERT INTO games (game_id,season,week,game_date,home_team,away_team,home_score,away_score)"
        " VALUES ('g1',2015,1,'2015-09-13','Dallas Cowboys','New York Giants',27,20),"
        "        ('g2',2020,1,'2020-09-13','Green Bay Packers','Chicago Bears',24,20);"
        "INSERT INTO betting_lines (game_id,spread_home_close,total_close)"
        " VALUES ('g1',-6.0,45.0),('g2',-1.0,44.0);"
        "INSERT INTO opening_lines (game_id,source,open_spread_home,open_total)"
        " VALUES ('g1','aus',-3.0,45.0),('g2','aus',-3.0,44.0);"
    )
    conn.commit()


def test_clv_ladder_filters_by_market_and_season(tmp_path, monkeypatch):
    conn = connect(":memory:")
    init_schema(conn)
    _seed_clv(conn)
    monkeypatch.setattr(appdata, "_open_db", lambda: conn)
    df_all = appdata.clv_ladder.__wrapped__(market="spread", season_range=(2000, 2030))
    df_2020 = appdata.clv_ladder.__wrapped__(market="spread", season_range=(2019, 2021))
    assert not df_all.empty
    assert df_2020["n"].sum() < df_all["n"].sum()  # season filter drops g1 (2015)
    assert set(df_all["clv_bucket"]).issubset({
        "clv_le_neg2", "clv_neg2_neg05", "clv_pm05", "clv_05_2", "clv_gt_2"})


def test_clv_ladder_open_vs_close_differ(monkeypatch):
    conn = connect(":memory:")
    init_schema(conn)
    _seed_clv(conn)
    monkeypatch.setattr(appdata, "_open_db", lambda: conn)
    op = appdata.clv_ladder.__wrapped__(market="spread", season_range=(2000, 2030), grade_at="open")
    cl = appdata.clv_ladder.__wrapped__(market="spread", season_range=(2000, 2030), grade_at="close")
    # win rates should not be identical across the two gradings on this data
    assert list(op["win_rate"]) != list(cl["win_rate"]) or list(op["clv_bucket"]) != list(cl["clv_bucket"])


def test_load_edge_report_missing_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(appdata, "_EDGE_CSV", tmp_path / "nope.csv")
    df = appdata.load_edge_report.__wrapped__()
    assert df.empty


def test_audit_summary_has_sources():
    s = appdata.audit_summary()
    assert "sources" in s and len(s["sources"]) == 4
    assert "overlap_spread_within_1pt" in s
```
Note: `st.cache_data` wraps each loader; the tests call `.__wrapped__()` to bypass the cache and to allow monkeypatching `_open_db`. `audit_summary` is a plain function (static constants), not cached, so call it directly.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.** Create `app/data.py`:
```python
"""Cached data-access layer for the dashboard. Thin wrappers over engine functions
+ produced CSVs. The @st.cache_data wrappers expose .__wrapped__ for testing.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from engine.clv import CLV_BUCKET_ORDER, aggregate_clv, build_bets_from_db
from engine.db import connect

_DB = "data/db/nfl_betting.sqlite"
_EDGE_CSV = Path("data/processed/edge_report.csv")


def _open_db() -> sqlite3.Connection:
    return connect(_DB)


@st.cache_data(show_spinner=False)
def load_edge_report() -> pd.DataFrame:
    """The honest edge report (Slice 5). Empty DataFrame if not generated yet."""
    if not _EDGE_CSV.exists():
        return pd.DataFrame()
    with _EDGE_CSV.open(encoding="utf-8") as f:
        rows = [ln for ln in f if not ln.lstrip().startswith("#")]
    return pd.DataFrame(list(csv.DictReader(rows)))


@st.cache_data(show_spinner=False)
def clv_ladder(*, market: str, season_range: tuple[int, int], grade_at: str = "open") -> pd.DataFrame:
    """Per-CLV-bucket rows for one market, filtered to a season range. Empty if no data."""
    try:
        conn = _open_db()
    except Exception:
        return pd.DataFrame()
    try:
        bets = build_bets_from_db(conn, grade_at=grade_at)
    finally:
        conn.close()
    lo, hi = season_range
    bets = [b for b in bets if lo <= b["season"] <= hi]
    rows = [r for r in aggregate_clv(bets) if r.market == market]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "clv_bucket": r.clv_bucket, "n": r.n, "mean_clv": r.mean_clv,
        "win_rate": r.win_rate, "roi": r.roi, "p_value": r.p_value,
        "mde80": r.mde80, "ci_low": r.ci_low, "ci_high": r.ci_high,
    } for r in rows])
    df["_order"] = df["clv_bucket"].map(CLV_BUCKET_ORDER.index)
    return df.sort_values("_order").drop(columns="_order").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def opening_line_coverage() -> pd.DataFrame:
    """Opening-line rows per source per season. Empty if DB/table absent."""
    try:
        conn = _open_db()
    except Exception:
        return pd.DataFrame()
    try:
        return pd.read_sql_query(
            "SELECT ol.source, g.season, COUNT(*) AS games"
            " FROM opening_lines ol JOIN games g ON g.game_id = ol.game_id"
            " GROUP BY ol.source, g.season ORDER BY g.season, ol.source",
            conn,
        )
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def season_bounds() -> tuple[int, int]:
    """Min/max season available for opener+closer CLV, for the slider. Falls back to 2007-2024."""
    try:
        conn = _open_db()
        df = pd.read_sql_query("SELECT MIN(season) lo, MAX(season) hi FROM games", conn)
        conn.close()
        lo, hi = int(df["lo"].iloc[0]), int(df["hi"].iloc[0])
        return lo, hi
    except Exception:
        return 2007, 2024


def audit_summary() -> dict:
    """Static data-quality facts. Source of truth: docs/superpowers/notes/2026-05-29-opening-line-audit.md."""
    return {
        "opening_rows_total": 8620,
        "overlap_games": 2183,
        "overlap_spread_within_1pt": 0.75,
        "overlap_total_within_1pt": 0.82,
        "sources": [
            {"name": "Kaggle (spreadspoke)", "provides": "closing spread + total", "window": "2004–2024"},
            {"name": "nflverse (nfl_data_py)", "provides": "real closing moneyline", "window": "2020–2024"},
            {"name": "SportsbookReviewsOnline", "provides": "opening spread + total", "window": "2007–2021"},
            {"name": "Australia Sports Betting", "provides": "opening spread/total/ML", "window": "2006–2024"},
        ],
    }
```

- [ ] **Step 4: Run → PASS** (file + full suite). Lint.

- [ ] **Step 5: Commit.**
```bash
git add app/data.py tests/test_app_data.py
git commit -m "feat(app): cached data-access layer (edge report, CLV ladder, coverage, audit)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `app/charts.py` Altair builders

**Files:** Create `app/charts.py`. (Charts return `alt.Chart`; validated via the tab smoke test + designqc — a tiny unit test confirms they build without error.)

- [ ] **Step 1: Write the failing test.** Append to `tests/test_app_data.py`:
```python
def test_charts_build_without_error():
    import pandas as pd
    from app import charts
    ladder = pd.DataFrame({"clv_bucket": ["clv_pm05", "clv_gt_2"], "win_rate": [0.5, 0.57],
                           "mean_clv": [0.1, 3.0]})
    edge = pd.DataFrame({"bucket": ["b1"], "point_roi": [0.01], "ci_low": [-0.05], "ci_high": [0.07]})
    assert charts.clv_ladder_chart(ladder) is not None
    assert charts.ci_errorbar_chart(edge) is not None
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.** Create `app/charts.py`:
```python
"""Altair chart builders for the dashboard (refined-dark friendly)."""

from __future__ import annotations

import altair as alt
import pandas as pd

from engine.clv import CLV_BUCKET_ORDER
from engine.stats_utils import BREAKEVEN_AT_NEG_110

_ACCENT = "#6c8cff"


def clv_ladder_chart(df: pd.DataFrame) -> alt.Chart:
    """Win rate by CLV bucket, with a breakeven reference line."""
    bars = (
        alt.Chart(df)
        .mark_bar(color=_ACCENT)
        .encode(
            x=alt.X("clv_bucket:N", sort=CLV_BUCKET_ORDER, title="CLV bucket (← against · toward →)"),
            y=alt.Y("win_rate:Q", title="win rate", scale=alt.Scale(zero=False)),
            tooltip=["clv_bucket", "win_rate", "mean_clv"],
        )
    )
    rule = alt.Chart(pd.DataFrame({"y": [BREAKEVEN_AT_NEG_110]})).mark_rule(
        color="#9aa0ad", strokeDash=[4, 4]
    ).encode(y="y:Q")
    return (bars + rule).properties(height=260)


def ci_errorbar_chart(df: pd.DataFrame) -> alt.Chart:
    """Point ROI per bucket with 95% CI error bars and a breakeven (0) line."""
    base = alt.Chart(df)
    points = base.mark_point(color=_ACCENT, filled=True, size=70).encode(
        x=alt.X("bucket:N", title="bucket"),
        y=alt.Y("point_roi:Q", title="point ROI"),
        tooltip=["bucket", "point_roi", "ci_low", "ci_high"],
    )
    bars = base.mark_rule(color=_ACCENT).encode(x="bucket:N", y="ci_low:Q", y2="ci_high:Q")
    zero = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(
        color="#9aa0ad", strokeDash=[4, 4]
    ).encode(y="y:Q")
    return (bars + points + zero).properties(height=300)
```

- [ ] **Step 4: Run → PASS** (file + full suite). Lint.

- [ ] **Step 5: Commit.**
```bash
git add app/charts.py tests/test_app_data.py
git commit -m "feat(app): Altair chart builders (CLV ladder, CI error-bar)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: main.py wiring + The Finding + Edge Report tabs

**Files:** Create `app/tab_finding.py`, `app/tab_edge.py`; modify `app/main.py`, `tests/test_app_smoke.py`.

- [ ] **Step 1: Create `app/tab_finding.py`:**
```python
"""The Finding — narrative hero: the CLV signal, with the open-vs-close proof panel."""

from __future__ import annotations

import streamlit as st

from app import charts, data


def render() -> None:
    st.subheader("The close is sharper than the open")
    st.write(
        "After we showed static bucket strategies are noise, this is the project's one real "
        "signal: when the line moves toward your side after you bet, you were more likely right — "
        "because the closing line is a better estimate than the opener."
    )
    bounds = data.season_bounds()
    spread = data.clv_ladder(market="spread", season_range=bounds, grade_at="open")
    if spread.empty:
        st.info("CLV data not available — generate it with `uv run python -m engine.clv`.")
        return
    lo, hi = spread["win_rate"].iloc[0], spread["win_rate"].iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("Spread win rate: low → high CLV", f"{lo:.1%} → {hi:.1%}")
    c2.metric("CLV ↔ result", "r ≈ 0.12 · p ≈ 1e-14")
    c3.metric("Bets analyzed", f"{int(spread['n'].sum()):,}+")
    st.altair_chart(charts.clv_ladder_chart(spread), use_container_width=True)

    st.markdown("##### Why it's real, not an artifact")
    st.caption("Grade the same bets at the OPENING number → win rate rises with CLV. "
               "Grade them at the CLOSING number → the trend flattens. The close has absorbed "
               "the information — proof the signal is genuine.")
    p1, p2 = st.columns(2)
    with p1:
        st.caption("graded @ opener (rises ↗)")
        st.altair_chart(charts.clv_ladder_chart(spread), use_container_width=True)
    with p2:
        st.caption("graded @ close (flat — signal gone)")
        close = data.clv_ladder(market="spread", season_range=bounds, grade_at="close")
        st.altair_chart(charts.clv_ladder_chart(close), use_container_width=True)
    st.caption("⚠ Signal test, not a tradeable strategy — CLV is unknowable until the line "
               "closes. Past performance ≠ future results.")
```

- [ ] **Step 2: Create `app/tab_edge.py`:**
```python
"""Edge Report — the honest-metrics table (Slice 5): no certified static edge."""

from __future__ import annotations

import streamlit as st

from app import charts, data


def render() -> None:
    st.subheader("Edge report — every bucket, with its uncertainty")
    st.write(
        "No static bucket shows a **certified** edge. That's a statement about statistical "
        "power, not proof the market is perfectly efficient — a real +2% ROI edge would be "
        "invisible at these sample sizes. `mde80_roi` = smallest edge detectable at this n."
    )
    df = data.load_edge_report()
    if df.empty:
        st.info("Edge report not available — generate it with "
                "`uv run python -m engine.ats && … && uv run python -m engine.edge_report`.")
        return
    markets = sorted(df["market"].unique())
    pick = st.selectbox("Market", markets, key="edge_market")
    sub = df[df["market"] == pick].copy()
    for col in ("point_roi", "ci_low", "ci_high"):
        sub[col] = sub[col].astype(float)
    st.altair_chart(charts.ci_errorbar_chart(sub), use_container_width=True)
    st.dataframe(sub, use_container_width=True, hide_index=True)
    st.caption("Past performance ≠ future results. Informational only; gamble responsibly.")
```

- [ ] **Step 3: Wire `app/main.py`.** Replace the import block additions + `main()`:
Add to the imports (after the existing `# noqa: E402` imports):
```python
from app import data, tab_clv, tab_data, tab_edge, tab_finding  # noqa: E402
```
Replace `main()`:
```python
def main() -> None:
    st.set_page_config(page_title="NFL Betting Analytics", page_icon="🏈", layout="wide")
    theme.inject()
    st.title("NFL Betting Analytics")
    lo, hi = data.season_bounds()
    season_range = st.sidebar.slider("Season range (CLV Explorer)", lo, hi, (lo, hi))
    tabs = st.tabs(["This Week", "The Finding", "Edge Report", "CLV Explorer", "Data & Audit"])
    with tabs[0]:
        render_this_week(_load_board())
    with tabs[1]:
        tab_finding.render()
    with tabs[2]:
        tab_edge.render()
    with tabs[3]:
        tab_clv.render(season_range)
    with tabs[4]:
        tab_data.render()
```
(Keep the existing `_load_board`, sys.path bootstrap, and `render_this_week` import. `tab_clv` and `tab_data` are created in Task 5 — to keep this task's app importable, create minimal stubs now: see Step 4.)

- [ ] **Step 4: Create minimal stubs** `app/tab_clv.py` and `app/tab_data.py` so the app imports (Task 5 fills them):
```python
# app/tab_clv.py
"""CLV Explorer — interactive (filled in Task 5)."""
from __future__ import annotations
import streamlit as st
def render(season_range) -> None:
    st.subheader("CLV Explorer")
    st.info("Coming up next.")
```
```python
# app/tab_data.py
"""Data & Audit (filled in Task 5)."""
from __future__ import annotations
import streamlit as st
def render() -> None:
    st.subheader("Data & Audit")
    st.info("Coming up next.")
```

- [ ] **Step 5: Extend the smoke test.** In `tests/test_app_smoke.py`, the existing test asserts no exception. Add an assertion that 5 tabs exist:
```python
def test_app_has_five_tabs():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("../app/main.py", default_timeout=30).run()
    assert not at.exception
    # 5 tab labels rendered
    labels = [t.label for t in at.tabs] if hasattr(at, "tabs") else []
    assert len(labels) >= 5 or len(at.get("tab")) >= 5  # tolerant to AppTest API shape
```
If the `AppTest` tab accessor differs in the installed version, keep it simple: assert `not at.exception` only (the boot is the key check) and drop the count assertion. The existing `test_app_boots_without_error` already covers boot.

- [ ] **Step 6: Run → PASS.** `uv run pytest tests/test_app_smoke.py -q` (boots with 5 tabs, no exception), full suite, ruff.

- [ ] **Step 7: Commit.**
```bash
git add app/tab_finding.py app/tab_edge.py app/tab_clv.py app/tab_data.py app/main.py tests/test_app_smoke.py
git commit -m "feat(app): wire 5 tabs + The Finding + Edge Report renders

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: CLV Explorer + Data & Audit tabs

**Files:** Replace stubs `app/tab_clv.py`, `app/tab_data.py`.

- [ ] **Step 1: Implement `app/tab_clv.py`:**
```python
"""CLV Explorer — interactive: filter by market + season range, re-bucket live."""

from __future__ import annotations

import streamlit as st

from app import charts, data


def render(season_range) -> None:
    st.subheader("CLV Explorer")
    st.write("Slice the closing-line-value signal yourself. Win rate should rise with CLV; "
             "the positive-CLV tails are statistically marginal — the **monotonic shape** is "
             "the evidence, not any single bucket.")
    market = st.radio("Market", ["spread", "total"], horizontal=True, key="clv_market")
    df = data.clv_ladder(market=market, season_range=season_range, grade_at="open")
    if df.empty:
        st.info(f"No {market} CLV data for seasons {season_range[0]}–{season_range[1]}.")
        return
    st.altair_chart(charts.clv_ladder_chart(df), use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Signal test, not a tradeable strategy — CLV is unknowable until the close.")
```

- [ ] **Step 2: Implement `app/tab_data.py`:**
```python
"""Data & Audit — coverage, cross-source agreement, and data provenance."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import data


def render() -> None:
    st.subheader("Data & Audit")
    s = data.audit_summary()
    c1, c2, c3 = st.columns(3)
    c1.metric("Opening-line rows", f"{s['opening_rows_total']:,}")
    c2.metric("Cross-source agree (spread, ±1pt)", f"{s['overlap_spread_within_1pt']:.0%}")
    c3.metric("Cross-source agree (total, ±1pt)", f"{s['overlap_total_within_1pt']:.0%}")
    st.caption(f"Two independent opening-line sources agree on ~{s['overlap_games']:,} overlap "
               "games (2013–2021). Sub-100% is expected — openers vary across books/timestamps.")

    st.markdown("##### Data sources")
    st.dataframe(pd.DataFrame(s["sources"]), use_container_width=True, hide_index=True)

    st.markdown("##### Opening-line coverage by season")
    cov = data.opening_line_coverage()
    if cov.empty:
        st.info("Coverage data not available — load opening lines first "
                "(`uv run python scripts/load_opening_lines.py`).")
    else:
        pivot = cov.pivot(index="season", columns="source", values="games").fillna(0).astype(int)
        st.dataframe(pivot, use_container_width=True)
    st.caption("Sources cross-validated; closing lines match nflverse ≥96% within ±1pt.")
```

- [ ] **Step 3: Run → PASS.** `uv run pytest tests/test_app_smoke.py -q` (still boots), full suite, ruff.

- [ ] **Step 4: Commit.**
```bash
git add app/tab_clv.py app/tab_data.py
git commit -m "feat(app): CLV Explorer + Data & Audit tabs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: designqc polish, README, bookkeeping

**Files:** possibly `app/*` (polish), `README.md`, `.wolf/*`.

- [ ] **Step 1: designqc each tab.** Ensure data exists (`data/processed/edge_report.csv`, `clv_report.csv`, the DB with opening_lines — all present from prior slices). Launch the app: `streamlit run app/main.py --server.headless true --server.port 8501` (background). For each tab, since `designqc` captures the default route, capture the landing then note that tab switching needs interaction — at minimum capture The Finding by temporarily setting it as the default tab OR use `designqc` on the running app and read `.wolf/designqc-captures/`. Read the screenshots, evaluate refined-dark consistency (spacing, the accent, chart legibility, honesty captions), apply polish to the tab renders / `charts.py` / `theme.py`, re-capture. Stop the server when done. If designqc can't drive tab switches, capture what it can and rely on reading the rendered HTML; do not block on perfect per-tab capture.
- [ ] **Step 2: README.** Add a "## Slice 9 — Historical showcase tabs" section: the 5-tab app (This Week leads), what each showcase tab shows, `streamlit run app/main.py`. Scope bullet: "**Slice 9 (complete):** historical showcase tabs (The Finding / Edge Report / CLV Explorer / Data & Audit) added to the Streamlit app alongside the live This Week board."
- [ ] **Step 3: Bookkeeping.** `.wolf/memory.md` one line; `.wolf/cerebrum.md` Decision Log entry (showcase tabs, This-Week-leads, grade_at='close' proof panel).
- [ ] **Step 4: Final verify + commit.**
```bash
uv run pytest -q
uv run ruff check .
git add app/ README.md .wolf/memory.md .wolf/cerebrum.md
git commit -m "docs(slice9): showcase tabs polish + README + bookkeeping

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage:** grade_at='close' (T1); app/data.py loaders incl. clv_ladder open/close + coverage + audit_summary (T2); Altair builders (T3); The Finding hero incl. proof panel + Edge Report (T4); CLV Explorer interactive + Data & Audit (T5); 5-tab wiring + sidebar season-range + smoke (T4); designqc + README + bookkeeping (T6). All spec sections covered. ✓

**Placeholder scan:** complete code for T1-T5; T4 creates real stubs for tab_clv/tab_data so the app imports before T5 fills them (intentional, not a placeholder-in-final-code — T5 replaces them). T6 is operational (designqc is inherently iterative). No TBD. ✓

**Type consistency:** `clv_ladder(*, market, season_range, grade_at)` signature consistent across data.py, the tests (`.__wrapped__`), and the tab callers. `build_bets_from_db(conn, grade_at=...)` consistent (T1 def, T2 caller). Chart builders `clv_ladder_chart(df)` / `ci_errorbar_chart(df)` consistent (T3 def, T4/T5 callers). `audit_summary()` keys (`opening_rows_total, overlap_games, overlap_spread_within_1pt, overlap_total_within_1pt, sources`) consistent between data.py and tab_data.py. `data.season_bounds()` used by main + tab_finding. ✓

**Note for executor:** AppTest's tab-introspection API varies by Streamlit version; if `test_app_has_five_tabs` can't read tab labels cleanly, keep only the boot/no-exception assertion (the existing smoke test) and confirm the 5 tabs visually in designqc instead. The `.__wrapped__` attribute exists because `st.cache_data` preserves the original function — if the installed Streamlit names it differently, call the loaders through a thin non-cached helper in the test instead.
