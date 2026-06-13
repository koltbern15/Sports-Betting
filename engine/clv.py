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
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

import pandas as pd

from engine.bucket_analysis import DISCLAIMER, compute_metrics
from engine.stats_utils import (
    mde_winrate_at_power,
    roi_from_win_prob,
    winrate_needed_for_ci,
)
from ingestion.loader import derive_ats_result, derive_total_result
from ingestion.opening_line_loader import canonical_opener_source

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


@dataclass(frozen=True)
class ClvRow:
    market: str  # 'spread' | 'total'
    clv_bucket: str
    n: int
    wins: int
    mean_clv: float
    win_rate: float
    roi: float  # roi_neg110 at the opener
    ci_low: float  # ROI units (win-rate Wilson bound -> ROI)
    ci_high: float
    p_value: float
    profitable_seasons_pct: float
    mde80: float  # smallest detectable edge at this n (ROI)
    breakeven_needed: float  # observed edge needed to clear breakeven CI (ROI)
    # decided (wins+losses) < INSUFFICIENT_SAMPLE_THRESHOLD; win_rate/p_value are noise.
    # Defaulted so positional ClvRow(...) construction (e.g. in tests) stays valid.
    insufficient_sample: bool = False


def aggregate_clv(bets: list[dict]) -> list[ClvRow]:
    """Aggregate per-bet records into CLV-bucket report rows.

    Each bet dict: {market, clv (float), result ('win'|'loss'|'push'), season (int)}.
    Reuses compute_metrics for win rate / ROI / CI / p-value / by-season, then adds
    mean_clv and the Slice 5 power columns. CIs are expressed in ROI for comparability.

    Basis note: `roi` is roi_neg110 (push-INCLUSIVE denominator, per spec), while
    `ci_low/ci_high` are roi_from_win_prob() of Wilson bounds on the push-EXCLUDED
    win rate. Algebraically roi_neg110 == roi_from_win_prob(win_rate) * (1 - push_rate),
    so the point estimate sits slightly toward zero from the CI's natural center by the
    push rate. The gap is sub-CI-noise in this data (point never escapes its own CI),
    but the two are not strictly the same basis — kept as-is to preserve the
    spec-mandated push-inclusive ROI; do not "fix" by silently re-centering either one.
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
        by_season_counts: dict[int, list[int]] = {}
        for b in items:
            if b["result"] in ("win", "loss"):
                cur = by_season_counts.setdefault(b["season"], [0, 0])
                cur[0] += 1 if b["result"] == "win" else 0
                cur[1] += 1
        by_season = {s: wl[0] / wl[1] for s, wl in by_season_counts.items() if wl[1] > 0}

        m = compute_metrics(bucket, wins, losses, pushes, by_season)
        rows.append(
            ClvRow(
                market=market,
                clv_bucket=bucket,
                n=m.n,
                wins=m.wins,
                mean_clv=mean(b["clv"] for b in items),
                win_rate=m.win_rate,
                roi=m.roi_neg110,
                ci_low=roi_from_win_prob(m.ci_low),
                ci_high=roi_from_win_prob(m.ci_high),
                p_value=m.p_value,
                profitable_seasons_pct=m.profitable_seasons_pct,
                mde80=roi_from_win_prob(mde_winrate_at_power(m.n)),
                breakeven_needed=roi_from_win_prob(winrate_needed_for_ci(m.n)),
                insufficient_sample=m.insufficient_sample,
            )
        )

    rows.sort(key=lambda r: (r.market, CLV_BUCKET_ORDER.index(r.clv_bucket)))
    return rows


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


def build_bets_from_db(conn: sqlite3.Connection, grade_at: str = "open") -> list[dict]:
    """Build per-game reference-bet records (spread + total) using the canonical opener.

    Picks the canonical opener source per game, applies the sanity clamp per market,
    computes CLV (always open vs close), and grades each bet at `grade_at`:
    'open' (default — the price you'd have taken) or 'close' (the sharper line).
    Grading at 'close' makes the CLV->result signal vanish — used to prove the
    open-graded signal is real, not a CLV/grade artifact.
    """
    df = pd.read_sql_query(_JOIN_SQL, conn)
    bets: list[dict] = []
    for _game_id, grp in df.groupby("game_id"):
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
            graded_sp = open_sp if grade_at == "open" else close_sp
            res = spread_bet_result(hs, as_, graded_sp)
            if res is not None:
                bets.append({"market": "spread", "clv": clv_spread(open_sp, close_sp),
                             "result": res, "season": season})

        open_tot = _f(row["open_total"])
        close_tot = _f(row["total_close"])
        if clamp_ok_total(open_tot) and clamp_ok_total(close_tot):
            graded_tot = open_tot if grade_at == "open" else close_tot
            res = total_bet_result(hs, as_, graded_tot)
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
