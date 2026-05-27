"""Moneyline-by-odds-bucket analysis (prices derived from closing spreads).

The Kaggle dataset has no historical sportsbook moneyline prices, so we derive
them from the closing spread via the standard normal-CDF model of NFL margins
plus a -110/-110-equivalent vig. All output clearly labels these as derived.
"""

from __future__ import annotations

import math

NFL_MARGIN_SIGMA: float = 13.86   # Burke / AdvancedNFL stats consensus
TARGET_OVERROUND: float = 1.04762  # matches -110/-110 implied probabilities
_EPS = 1e-6


def _prob_to_american(p: float) -> int:
    """Convert an implied probability (0,1) to integer American odds (banker rounding)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"probability must be in (0,1), got {p}")
    if p >= 0.5:
        return round(-100.0 * p / (1.0 - p))
    return round(100.0 * (1.0 - p) / p)


def derive_ml_from_spread(spread_home_close: float | None) -> tuple[int, int] | None:
    """Convert a closing home-perspective spread to derived (home_ml, away_ml) American odds.

    Math:
      P_home_no_vig = Phi(-spread / sigma)   where Phi is the standard normal CDF
      P_*_vig       = P_*_no_vig * 1.04762   (proportional vig)
      ML            = American odds equivalent of P_*_vig
    Returns None if input is None or NaN.
    """
    if spread_home_close is None:
        return None
    if isinstance(spread_home_close, float) and math.isnan(spread_home_close):
        return None
    p_home_nv = 0.5 * (1.0 + math.erf(-spread_home_close / (NFL_MARGIN_SIGMA * math.sqrt(2.0))))
    p_away_nv = 1.0 - p_home_nv
    p_home_vig = min(max(p_home_nv * TARGET_OVERROUND, _EPS), 1.0 - _EPS)
    p_away_vig = min(max(p_away_nv * TARGET_OVERROUND, _EPS), 1.0 - _EPS)
    return (_prob_to_american(p_home_vig), _prob_to_american(p_away_vig))


BUCKET_ORDER_ML: list[str] = [
    "ml_heavy_fav",
    "ml_big_fav",
    "ml_mid_fav",
    "ml_small_fav",
    "ml_slight_fav",
    "ml_pickem",
    "ml_slight_dog",
    "ml_small_dog",
    "ml_mid_dog",
    "ml_big_dog",
    "ml_heavy_dog",
]


def bucket_ml(ml_price: int | None) -> str | None:
    """Bucket an American moneyline price into one of 11 categories.

    Favorites carry negative odds; underdogs positive. Pickem covers -109..+109.
    """
    if ml_price is None:
        return None
    if ml_price <= -300:
        return "ml_heavy_fav"
    if ml_price <= -250:
        return "ml_big_fav"
    if ml_price <= -180:
        return "ml_mid_fav"
    if ml_price <= -130:
        return "ml_small_fav"
    if ml_price <= -110:
        return "ml_slight_fav"
    if ml_price < +110:
        return "ml_pickem"
    if ml_price < +130:
        return "ml_slight_dog"
    if ml_price < +180:
        return "ml_small_dog"
    if ml_price < +250:
        return "ml_mid_dog"
    if ml_price < +300:
        return "ml_big_dog"
    return "ml_heavy_dog"
