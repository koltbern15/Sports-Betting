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
from dataclasses import dataclass
from statistics import mean

from engine.bucket_analysis import compute_metrics
from engine.stats_utils import (
    mde_winrate_at_power,
    roi_from_win_prob,
    winrate_needed_for_ci,
)
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
            )
        )

    rows.sort(key=lambda r: (r.market, CLV_BUCKET_ORDER.index(r.clv_bucket)))
    return rows
