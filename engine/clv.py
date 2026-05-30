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
