# NFL Betting Analytics — Slice 7: CLV Engine + Validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute per-game closing-line value (CLV) for spread and total (opener vs closer), grade each reference bet at the opening number, bucket by CLV, and report whether positive CLV predicts covering the opener — in the Slice 5 honest-metrics shape, framed explicitly as a signal test (not a tradeable strategy).

**Architecture:** One new module `engine/clv.py`. Pure CLV/grading/bucketing helpers (Task 1), a pure aggregator over per-game records that reuses `engine.bucket_analysis.compute_metrics` and the Slice 5 power helpers (Task 2), then DB orchestration + CSV report + CLI (Task 3), then the real run + findings doc (Task 4). Reuses `ingestion.loader.derive_ats_result`/`derive_total_result` for opener grading and `ingestion.opening_line_loader.canonical_opener_source` for opener selection.

**Tech Stack:** Python 3.11, `sqlite3` (stdlib), `pandas`, `pytest`, `uv`, `ruff`. No new dependencies.

**Scope:** spread + total only (the committed core). Moneyline CLV is a deferred stretch — NOT in this plan; a short note in Task 4 records whether it's worth a follow-on.

**Key reused signatures (verified):**
- `derive_ats_result(home_score, away_score, spread_home_close) -> 'cover'|'loss'|'push'|None` (grades the HOME side at any spread).
- `derive_total_result(home_score, away_score, total_close) -> 'over'|'under'|'push'|None` (grades the OVER at any total).
- `compute_metrics(bucket, wins, losses, pushes, by_season=None, *, payouts=None) -> BucketMetrics` with fields `n, wins, losses, pushes, win_rate, push_rate, roi_neg110, roi_neg105, p_value, ci_low, ci_high, by_season, profitable_seasons_pct` (ci_low/ci_high are Wilson bounds on win rate).
- `stats_utils.mde_winrate_at_power(n)`, `winrate_needed_for_ci(n)`, `roi_from_win_prob(p)` (Slice 5).
- `canonical_opener_source(season) -> 'sbr'|'aus'`.
- Schema: `opening_lines(game_id, source, open_spread_home, open_total, ...)`, `betting_lines(game_id, spread_home_close, total_close, ...)`, `games(game_id, season, home_score, away_score, ...)`.

**CLV sign conventions (unit-pinned):**
- `clv_spread = open_spread_home − close_spread_home` (home reference bet; positive = close moved toward home).
- `clv_total = close_total − open_total` (over reference bet; positive = close moved up, toward the over).
- Both: positive = the close moved in the reference bet's favor.

---

## File structure

| File | Responsibility | Lifecycle |
|---|---|---|
| `engine/clv.py` | CLV math + grading + bucketing (T1), aggregator (T2), DB orchestration + CSV + CLI (T3) | NEW |
| `tests/test_clv.py` | All CLV unit + integration tests | NEW |
| `docs/superpowers/notes/2026-05-30-clv-findings.md` | The CLV→results finding (written from the real run) | NEW |
| `README.md` | Slice 7 section + headline | MODIFY |

---

## Task 1: CLV math, grading, and bucketing helpers

**Files:**
- Create: `engine/clv.py`
- Test: `tests/test_clv.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_clv.py`:
```python
"""Tests for engine.clv — pure CLV math, grading, bucketing."""

from __future__ import annotations

import math

from engine.clv import (
    clamp_ok_spread,
    clamp_ok_total,
    clv_bucket,
    clv_spread,
    clv_total,
    spread_bet_result,
    total_bet_result,
)


def test_clv_spread_positive_when_close_more_home_favored():
    # home opens -3, closes -5 -> +2 (you laid fewer points than the close)
    assert clv_spread(-3.0, -5.0) == 2.0


def test_clv_spread_negative_when_line_moves_against_home():
    # home opens -3, closes -1 -> -2
    assert clv_spread(-3.0, -1.0) == -2.0


def test_clv_total_positive_when_close_moves_up():
    # over opens 45, closes 47 -> +2 (you bought the over at a lower bar)
    assert clv_total(45.0, 47.0) == 2.0


def test_clv_total_zero_on_no_move():
    assert clv_total(45.0, 45.0) == 0.0


def test_clamp_spread_band():
    assert clamp_ok_spread(-26.5) is True
    assert clamp_ok_spread(28.0) is True
    assert clamp_ok_spread(40.0) is False
    assert clamp_ok_spread(None) is False


def test_clamp_total_band():
    assert clamp_ok_total(25.0) is True
    assert clamp_ok_total(75.0) is True
    assert clamp_ok_total(541.0) is False
    assert clamp_ok_total(10.0) is False
    assert clamp_ok_total(None) is False


def test_spread_bet_result_home_cover_is_win():
    # home -3 at opener; home wins by 7 -> covers -> win
    assert spread_bet_result(27, 20, -3.0) == "win"
    # home -3; home wins by 1 -> -3 spread => adjusted -2 -> loss
    assert spread_bet_result(21, 20, -3.0) == "loss"
    # home -3; home wins by exactly 3 -> push
    assert spread_bet_result(23, 20, -3.0) == "push"
    # missing score -> None
    assert spread_bet_result(None, 20, -3.0) is None


def test_total_bet_result_over_is_win():
    # over 45; combined 50 -> over -> win
    assert total_bet_result(30, 20, 45.0) == "win"
    # over 45; combined 40 -> under -> loss
    assert total_bet_result(20, 20, 45.0) == "loss"
    # over 45; combined exactly 45 -> push
    assert total_bet_result(25, 20, 45.0) == "push"


def test_clv_bucket_edges():
    assert clv_bucket(-3.0) == "clv_le_neg2"
    assert clv_bucket(-2.0) == "clv_le_neg2"   # lower edge inclusive at top of first bin
    assert clv_bucket(-1.0) == "clv_neg2_neg05"
    assert clv_bucket(0.0) == "clv_pm05"
    assert clv_bucket(0.5) == "clv_pm05"
    assert clv_bucket(1.0) == "clv_05_2"
    assert clv_bucket(2.0) == "clv_05_2"
    assert clv_bucket(5.0) == "clv_gt_2"
    assert clv_bucket(float("nan")) is None
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_clv.py -q`
Expected: FAIL / ImportError.

- [ ] **Step 3: Implement helpers**

Create `engine/clv.py`:
```python
"""Closing-line value (CLV) engine.

Computes per-game CLV for spread and total (canonical opener vs closer), grades
each reference bet at the OPENING number, buckets by CLV, and reports whether
positive CLV predicts covering the opener — i.e. whether the close is sharper
than the open. This VALIDATES signal; it is NOT a tradeable strategy (CLV is
unknown until the close).

Reference bets: spread = HOME at the opener; total = OVER at the opener.
  clv_spread = open_spread_home - close_spread_home   (positive = close toward home)
  clv_total  = close_total - open_total                (positive = close toward over)
"""

from __future__ import annotations

import math

from ingestion.loader import derive_ats_result, derive_total_result

_SPREAD_CLAMP = 28.0
_TOTAL_LO, _TOTAL_HI = 25.0, 75.0


def clv_spread(open_spread_home: float, close_spread_home: float) -> float:
    """Home-side CLV in points. Positive = you got a better number than the close."""
    return open_spread_home - close_spread_home


def clv_total(open_total: float, close_total: float) -> float:
    """Over-side CLV in points. Positive = close moved up, favoring the over."""
    return close_total - open_total


def clamp_ok_spread(x: float | None) -> bool:
    """True if x is a plausible opening spread magnitude (<= 28)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return False
    return abs(x) <= _SPREAD_CLAMP


def clamp_ok_total(x: float | None) -> bool:
    """True if x is a plausible opening total (25..75)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return False
    return _TOTAL_LO <= x <= _TOTAL_HI


def spread_bet_result(
    home_score: int | None, away_score: int | None, open_spread_home: float
) -> str | None:
    """Grade the HOME bet at the opening spread -> 'win'|'loss'|'push'|None."""
    r = derive_ats_result(home_score, away_score, open_spread_home)
    if r is None:
        return None
    return {"cover": "win", "loss": "loss", "push": "push"}[r]


def total_bet_result(
    home_score: int | None, away_score: int | None, open_total: float
) -> str | None:
    """Grade the OVER bet at the opening total -> 'win'|'loss'|'push'|None."""
    r = derive_total_result(home_score, away_score, open_total)
    if r is None:
        return None
    return {"over": "win", "under": "loss", "push": "push"}[r]


# CLV buckets, ordered most-negative to most-positive. (lo, hi, label] with lo<clv<=hi.
_CLV_BINS: list[tuple[float, float, str]] = [
    (-math.inf, -2.0, "clv_le_neg2"),
    (-2.0, -0.5, "clv_neg2_neg05"),
    (-0.5, 0.5, "clv_pm05"),
    (0.5, 2.0, "clv_05_2"),
    (2.0, math.inf, "clv_gt_2"),
]

CLV_BUCKET_ORDER: list[str] = [label for _lo, _hi, label in _CLV_BINS]


def clv_bucket(clv: float) -> str | None:
    """Label the CLV bin (lo < clv <= hi). Returns None for NaN."""
    if isinstance(clv, float) and math.isnan(clv):
        return None
    for lo, hi, label in _CLV_BINS:
        if lo < clv <= hi:
            return label
    return None
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_clv.py -q` then `uv run pytest -q`.
Expected: PASS, full suite green.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check engine/clv.py tests/test_clv.py
git add engine/clv.py tests/test_clv.py
git commit -m "feat(clv): CLV math, opener grading, bucketing helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: CLV aggregator (records -> report rows)

**Files:**
- Modify: `engine/clv.py` (append)
- Test: `tests/test_clv.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_clv.py`. Add `ClvRow` and `aggregate_clv` to the import block at the top.
```python
def _bet(market, clv, result, season):
    return {"market": market, "clv": clv, "result": result, "season": season}


def test_aggregate_groups_by_market_and_bucket():
    bets = [
        _bet("spread", 3.0, "win", 2015),   # clv_gt_2
        _bet("spread", 3.0, "win", 2016),
        _bet("spread", 3.0, "loss", 2017),
        _bet("spread", -3.0, "loss", 2015),  # clv_le_neg2
        _bet("total", 1.0, "win", 2015),     # clv_05_2
    ]
    rows = aggregate_clv(bets)
    by_key = {(r.market, r.clv_bucket): r for r in rows}
    assert by_key[("spread", "clv_gt_2")].n == 3
    assert by_key[("spread", "clv_gt_2")].wins == 2
    assert by_key[("spread", "clv_gt_2")].mean_clv == 3.0
    assert by_key[("spread", "clv_le_neg2")].n == 1
    assert ("total", "clv_05_2") in by_key


def test_aggregate_win_rate_and_power_columns_present():
    bets = [_bet("spread", 1.0, "win" if i % 2 == 0 else "loss", 2015 + (i % 3)) for i in range(10)]
    rows = aggregate_clv(bets)
    r = next(r for r in rows if r.market == "spread")
    assert 0.0 <= r.win_rate <= 1.0
    assert isinstance(r.mde80, float)
    assert isinstance(r.breakeven_needed, float)
    # ci bounds are ROI-expressed via roi_from_win_prob; finite for n>0
    assert math.isfinite(r.ci_low) and math.isfinite(r.ci_high)


def test_aggregate_pushes_excluded_from_winrate_denominator():
    bets = [
        _bet("spread", 1.0, "win", 2015),
        _bet("spread", 1.0, "loss", 2015),
        _bet("spread", 1.0, "push", 2015),
    ]
    rows = aggregate_clv(bets)
    r = rows[0]
    assert r.n == 3
    assert r.win_rate == 0.5  # 1 win / (1 win + 1 loss); push excluded from denom


def test_aggregate_rows_sorted_market_then_bucket_order():
    bets = [
        _bet("spread", 3.0, "win", 2015),
        _bet("spread", -3.0, "win", 2015),
        _bet("total", 3.0, "win", 2015),
    ]
    rows = aggregate_clv(bets)
    spread_buckets = [r.clv_bucket for r in rows if r.market == "spread"]
    # clv_le_neg2 must come before clv_gt_2
    assert spread_buckets.index("clv_le_neg2") < spread_buckets.index("clv_gt_2")
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_clv.py -q` → FAIL/ImportError.

- [ ] **Step 3: Implement the aggregator**

Append to `engine/clv.py`. Add these imports to the top import block:
```python
from dataclasses import dataclass
from statistics import mean

from engine.bucket_analysis import compute_metrics
from engine.stats_utils import (
    mde_winrate_at_power,
    roi_from_win_prob,
    winrate_needed_for_ci,
)
```
Then append:
```python
@dataclass(frozen=True)
class ClvRow:
    market: str  # 'spread' | 'total'
    clv_bucket: str
    n: int
    mean_clv: float
    win_rate: float
    roi: float  # roi_neg110 at the opener
    ci_low: float  # ROI units (win-rate Wilson bound -> ROI)
    ci_high: float
    p_value: float
    profitable_seasons_pct: float
    mde80: float  # smallest detectable edge at this n (ROI)
    breakeven_needed: float  # observed edge needed to clear breakeven CI (ROI)


def aggregate_clv(bets: list[dict]) -> list[ClvRow]:
    """Aggregate per-bet records into CLV-bucket report rows.

    Each bet dict: {market, clv (float), result ('win'|'loss'|'push'), season (int)}.
    Reuses compute_metrics for win rate / ROI / CI / p-value / by-season, then adds
    mean_clv and the Slice 5 power columns. CIs are expressed in ROI for comparability.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for b in bets:
        bucket = clv_bucket(b["clv"])
        if bucket is None:
            continue
        groups.setdefault((b["market"], bucket), []).append(b)

    rows: list[ClvRow] = []
    for (market, bucket), items in groups.items():
        wins = sum(1 for b in items if b["result"] == "win")
        losses = sum(1 for b in items if b["result"] == "loss")
        pushes = sum(1 for b in items if b["result"] == "push")
        # per-season win rate for profitable_seasons_pct
        by_season_counts: dict[int, list[int]] = {}
        for b in items:
            if b["result"] in ("win", "loss"):
                w, total = by_season_counts.setdefault(b["season"], [0, 0])
                by_season_counts[b["season"]] = [w + (b["result"] == "win"), total + 1]
        by_season = {s: wl[0] / wl[1] for s, wl in by_season_counts.items() if wl[1] > 0}

        m = compute_metrics(bucket, wins, losses, pushes, by_season)
        rows.append(
            ClvRow(
                market=market,
                clv_bucket=bucket,
                n=m.n,
                mean_clv=mean(b["clv"] for b in items),
                win_rate=m.win_rate,
                roi=m.roi_neg110,
                ci_low=roi_from_win_prob(m.ci_low),
                ci_high=roi_from_win_prob(m.ci_high),
                p_value=m.p_value,
                profitable_seasons_pct=m.profitable_seasons_pct,
                mde80=roi_from_win_prob(mde_winrate_at_power(m.n)),
                breakeven_needed=roi_from_win_prob(winrate_needed_for_ci(m.n)),
            )
        )

    rows.sort(key=lambda r: (r.market, CLV_BUCKET_ORDER.index(r.clv_bucket)))
    return rows
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_clv.py -q` then `uv run pytest -q`.
Expected: PASS, full suite green.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check engine/clv.py tests/test_clv.py
git add engine/clv.py tests/test_clv.py
git commit -m "feat(clv): CLV-bucket aggregator (reuses compute_metrics + power helpers)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: DB orchestration + CSV report + CLI

**Files:**
- Modify: `engine/clv.py` (append)
- Test: `tests/test_clv.py` (append)

- [ ] **Step 1: Write the failing test (in-memory DB)**

Append to `tests/test_clv.py`. Add `build_bets_from_db`, `write_clv_csv`, `_HEADER` to the import block.
```python
from engine.db import connect, init_schema
from ingestion.opening_line_loader import canonical_opener_source  # noqa: F401  (used indirectly)


def _seed(conn, game_id, season, hs, as_, src, open_sp, open_tot, close_sp, close_tot):
    conn.execute(
        "INSERT INTO games (game_id, season, week, game_date, home_team, away_team, home_score, away_score)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (game_id, season, 1, f"{season}-09-13", "Home Team X", "Away Team Y", hs, as_),
    )
    conn.execute(
        "INSERT INTO betting_lines (game_id, spread_home_close, total_close) VALUES (?,?,?)",
        (game_id, close_sp, close_tot),
    )
    conn.execute(
        "INSERT INTO opening_lines (game_id, source, open_spread_home, open_total) VALUES (?,?,?,?)",
        (game_id, src, open_sp, open_tot),
    )


def test_build_bets_from_db_uses_canonical_source_and_clamp():
    conn = connect(":memory:")
    init_schema(conn)
    # 2018 -> canonical 'aus'. Seed both sources; only 'aus' should be used.
    _seed(conn, "g1", 2018, 27, 20, "aus", -3.0, 45.0, -5.0, 47.0)
    _seed(conn, "g1", 2018, 27, 20, "sbr", -10.0, 99.0, -5.0, 47.0)  # sbr ignored; total 99 would clamp out anyway
    bets = build_bets_from_db(conn)
    spread_bets = [b for b in bets if b["market"] == "spread"]
    total_bets = [b for b in bets if b["market"] == "total"]
    assert len(spread_bets) == 1
    assert spread_bets[0]["clv"] == 2.0       # open -3 - close -5
    assert spread_bets[0]["result"] == "win"  # home wins by 7, covers -3
    assert total_bets[0]["clv"] == 2.0        # close 47 - open 45
    conn.close()


def test_build_bets_skips_bad_opener_total_only_for_that_market():
    conn = connect(":memory:")
    init_schema(conn)
    # total opener 541 is implausible -> total bet dropped; spread still computes
    _seed(conn, "g1", 2018, 27, 20, "aus", -3.0, 541.0, -5.0, 47.0)
    bets = build_bets_from_db(conn)
    assert any(b["market"] == "spread" for b in bets)
    assert not any(b["market"] == "total" for b in bets)
    conn.close()


def test_write_clv_csv_has_header_and_disclaimer(tmp_path):
    from engine.clv import ClvRow, write_clv_csv
    rows = [ClvRow("spread", "clv_gt_2", 100, 3.2, 0.55, 0.05, 0.01, 0.10, 0.03, 0.6, 0.2, 0.18)]
    out = tmp_path / "clv_report.csv"
    write_clv_csv(rows, out)
    text = out.read_text(encoding="utf-8")
    assert "market,clv_bucket,n,mean_clv,win_rate,roi,ci_low,ci_high,p_value,profitable_seasons_pct,mde80,breakeven_needed" in text
    assert "# CLV report" in text
    assert "signal test" in text.lower()  # disclaimer says not a strategy
    assert "spread,clv_gt_2,100" in text
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_clv.py -q` → FAIL/ImportError.

- [ ] **Step 3: Implement DB orchestration + writer + CLI**

Append to `engine/clv.py`. Add to the top import block:
```python
import sqlite3
from pathlib import Path

import pandas as pd

from engine.bucket_analysis import DISCLAIMER
from ingestion.opening_line_loader import canonical_opener_source
```
Then append:
```python
_JOIN_SQL = """
SELECT g.game_id, g.season, g.home_score, g.away_score,
       o.source, o.open_spread_home, o.open_total,
       b.spread_home_close, b.total_close
FROM games g
JOIN opening_lines o ON o.game_id = g.game_id
JOIN betting_lines b ON b.game_id = g.game_id
WHERE g.home_score IS NOT NULL AND g.away_score IS NOT NULL
"""


def _f(v) -> float | None:
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def build_bets_from_db(conn: sqlite3.Connection) -> list[dict]:
    """Build per-game reference-bet records (spread + total) using the canonical opener.

    Picks the canonical opener source per game, applies the sanity clamp per market,
    computes CLV, and grades each bet at the OPENING number.
    """
    df = pd.read_sql_query(_JOIN_SQL, conn)
    bets: list[dict] = []
    for game_id, grp in df.groupby("game_id"):
        season = int(grp["season"].iloc[0])
        want = canonical_opener_source(season)
        canon = grp[grp["source"] == want]
        if canon.empty:
            continue
        row = canon.iloc[0]
        hs = int(row["home_score"])
        as_ = int(row["away_score"])

        open_sp = _f(row["open_spread_home"])
        close_sp = _f(row["spread_home_close"])
        if clamp_ok_spread(open_sp) and clamp_ok_spread(close_sp):
            res = spread_bet_result(hs, as_, open_sp)
            if res is not None:
                bets.append({"market": "spread", "clv": clv_spread(open_sp, close_sp),
                             "result": res, "season": season})

        open_tot = _f(row["open_total"])
        close_tot = _f(row["total_close"])
        if clamp_ok_total(open_tot) and clamp_ok_total(close_tot):
            res = total_bet_result(hs, as_, open_tot)
            if res is not None:
                bets.append({"market": "total", "clv": clv_total(open_tot, close_tot),
                             "result": res, "season": season})
    return bets


_HEADER = (
    "market,clv_bucket,n,mean_clv,win_rate,roi,ci_low,ci_high,"
    "p_value,profitable_seasons_pct,mde80,breakeven_needed"
)


def _fmt(x: float, prec: int = 6) -> str:
    return "" if isinstance(x, float) and math.isnan(x) else f"{x:.{prec}f}"


def write_clv_csv(rows: list[ClvRow], path: str | Path) -> None:
    """Write the CLV report with explanatory note + disclaimer."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CLV report: per-CLV-bucket win rate at the opener. Tests whether the close "
        "is sharper than the open (positive CLV -> covers the opener more often).",
        "# This is a SIGNAL TEST, not a tradeable strategy: CLV is unknown until the line closes.",
        f"# {DISCLAIMER}",
        _HEADER,
    ]
    for r in rows:
        lines.append(
            f"{r.market},{r.clv_bucket},{r.n},{_fmt(r.mean_clv,4)},{_fmt(r.win_rate,4)},"
            f"{_fmt(r.roi)},{_fmt(r.ci_low)},{_fmt(r.ci_high)},{_fmt(r.p_value)},"
            f"{_fmt(r.profitable_seasons_pct,4)},{_fmt(r.mde80)},{_fmt(r.breakeven_needed)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


DEFAULT_OUT_CSV = "data/processed/clv_report.csv"


def _main() -> int:
    """CLI: uv run python -m engine.clv"""
    from engine.db import connect

    conn = connect("data/db/nfl_betting.sqlite")
    try:
        bets = build_bets_from_db(conn)
    finally:
        conn.close()
    if not bets:
        print("No joinable opener+closer games found. Load Slice 6 opening lines first.")
        return 1
    rows = aggregate_clv(bets)
    write_clv_csv(rows, DEFAULT_OUT_CSV)
    n_spread = sum(1 for b in bets if b["market"] == "spread")
    n_total = sum(1 for b in bets if b["market"] == "total")
    print(f"CLV report: {n_spread} spread bets, {n_total} total bets across "
          f"{len(rows)} CLV buckets.")
    for r in rows:
        print(f"  {r.market:6} {r.clv_bucket:14} n={r.n:5} mean_clv={r.mean_clv:+.2f} "
              f"win%={r.win_rate:.4f} roi={r.roi:+.4f} p={r.p_value:.3f}")
    print(f"\n{DISCLAIMER}")
    print(f"\nCSV written to {DEFAULT_OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_clv.py -q` then `uv run pytest -q`.
Expected: PASS, full suite green.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check engine/clv.py tests/test_clv.py
git add engine/clv.py tests/test_clv.py
git commit -m "feat(clv): DB orchestration + CSV report + CLI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Real run, findings note, README, bookkeeping

**Files:**
- Create: `docs/superpowers/notes/2026-05-30-clv-findings.md`
- Modify: `README.md`, `.wolf/memory.md`, `.wolf/cerebrum.md`

- [ ] **Step 1: Run the CLV report on the real DB**

Run: `uv run python -m engine.clv`
Expected: prints the per-bucket table (spread + total, 5 CLV buckets each) and writes `data/processed/clv_report.csv`. Read the CSV. Record the headline: **does win rate rise monotonically with CLV across the buckets, and do the positive-CLV buckets (`clv_05_2`, `clv_gt_2`) clear 52.4% at the opener?** Note the n per bucket and whether the trend is statistically meaningful (p-values, and the `mde80` power column — is n big enough to detect the effect?).

- [ ] **Step 2: Write the findings note**

Create `docs/superpowers/notes/2026-05-30-clv-findings.md` documenting: the method (one reference bet per game, graded at the opener), the per-bucket win-rate/ROI table for spread and total (paste the real numbers), the monotonicity verdict, whether positive CLV beats breakeven at the opener, the power read (is the sample big enough), and the honest framing (signal test, not a strategy). State explicitly whether the close is sharper than the open in this data. Note the ML-CLV deferral and whether the spread/total result suggests it's worth a follow-on.

- [ ] **Step 3: Update README**

Add a "## Slice 7 — CLV engine + validation" section after Slice 6: what it does, the CLV definitions, the workflow command (`uv run python -m engine.clv`), the `clv_report.csv` columns, and the one-line headline from the findings note. Add a Scope bullet: "**Slice 7 (complete):** CLV engine — per-game CLV (spread+total) + validation of whether positive CLV predicts covering the opener, in the honest-metrics shape. Signal test, not a strategy." Keep the Deferred bullet for the dashboard (Slice 8) and ML-CLV.

- [ ] **Step 4: OpenWolf bookkeeping**

- `.wolf/memory.md`: append one Slice 7 summary line (re-read top first; retry once if the hook modified it).
- `.wolf/cerebrum.md`: Decision Log entry (2026-05-30): "Slice 7 built the CLV engine — one reference bet/game (home/over) graded at the opener, bucketed by CLV, honest-metrics report. Tests whether the close is sharper than the open. <headline verdict>."

- [ ] **Step 5: Final verification + commit**

```bash
uv run pytest -q
uv run ruff check .
git add README.md .wolf/memory.md .wolf/cerebrum.md docs/superpowers/notes/2026-05-30-clv-findings.md
git status   # confirm NO data/db or data/processed CSV staged if gitignored
git commit -m "docs(slice7): CLV findings + README + bookkeeping

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage:**
- CLV definitions (clv_spread/clv_total, signs) → Task 1 helpers, unit-pinned. ✓
- Reference bet = home/over at opener, graded at the OPENING number → Task 1 `spread_bet_result`/`total_bet_result` (pass open line); Task 3 `build_bets_from_db`. ✓
- Bucket by CLV + report n/mean CLV/win rate/ROI/CI/p/power, honest-metrics shape (no gate) → Task 2 aggregator + Task 3 writer. ✓
- Opener sanity clamp, per-market, counted → Task 1 `clamp_ok_*`, Task 3 application (drops a market, keeps the other). ✓
- Canonical opener + Kaggle closer pairing → Task 3 `canonical_opener_source`. ✓
- Continuous, no binary gate; disclaimer "signal test not strategy" → Task 3 writer notes. ✓
- Real run + findings + README + bookkeeping → Task 4. ✓
- ML deferred (not in plan; noted in Task 4 findings). ✓

**Placeholder scan:** every code step shows full code; commands have expected output; no TBD. ✓

**Type consistency:** `ClvRow` fields identical in the dataclass (T2), the writer (T3), and the test constructor (T3 Step 1). Helper names consistent: `clv_spread`, `clv_total`, `clamp_ok_spread`, `clamp_ok_total`, `spread_bet_result`, `total_bet_result`, `clv_bucket`, `CLV_BUCKET_ORDER` (T1) used by `aggregate_clv` (T2) and `build_bets_from_db` (T3); `aggregate_clv`, `build_bets_from_db`, `write_clv_csv`, `_HEADER` (T2/T3) used by tests + `_main`. Bet-dict keys `market/clv/result/season` consistent between `build_bets_from_db` and `aggregate_clv`. ✓

**One note:** `build_bets_from_db` groups by `game_id` and picks the canonical source; if a game has only the non-canonical source it is skipped (counted implicitly by absence). The findings note (Task 4) should report total bets per market so coverage is visible.
