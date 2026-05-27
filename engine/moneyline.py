"""Moneyline-by-odds-bucket analysis (prices derived from closing spreads).

The Kaggle dataset has no historical sportsbook moneyline prices, so we derive
them from the closing spread via the standard normal-CDF model of NFL margins
plus a -110/-110-equivalent vig. All output clearly labels these as derived.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

import pandas as pd

from engine.bucket_analysis import BucketMetrics, compute_metrics

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


def _payout_for_bet(ml_price: int, won: bool | None) -> float:
    """Net PnL of a 1-unit moneyline bet.

    won=True  → +odds/100 if positive American, +100/|odds| if negative
    won=False → -1.0
    won=None  → 0.0 (push, e.g. NFL tie)
    """
    if won is None:
        return 0.0
    if not won:
        return -1.0
    if ml_price > 0:
        return ml_price / 100.0
    return 100.0 / abs(ml_price)


def _outcome(home_score: int, away_score: int, side: str) -> bool | None:
    """Return True if `side` won outright, False if lost, None for tie."""
    if home_score == away_score:
        return None
    home_won = home_score > away_score
    return home_won if side == "home" else (not home_won)


@dataclass
class MoneylineReport:
    rows: list[BucketMetrics]


def moneyline_by_odds_bucket(conn: sqlite3.Connection) -> MoneylineReport:
    """Aggregate moneyline outcomes into 11 derived-ML buckets.

    Each game contributes two bet rows (home perspective + away perspective).
    Prices are derived from spread via derive_ml_from_spread().
    ROI is dollar-weighted using per-bet payouts because prices vary across rows.
    """
    df = pd.read_sql_query(
        """
        SELECT g.season, b.spread_home_close, g.home_score, g.away_score
        FROM games g
        JOIN betting_lines b ON b.game_id = g.game_id
        WHERE b.spread_home_close IS NOT NULL
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
        """,
        conn,
    )

    records: list[dict] = []
    for _idx, row in df.iterrows():
        derived = derive_ml_from_spread(float(row["spread_home_close"]))
        if derived is None:
            continue
        ml_home, ml_away = derived
        for side, ml in (("home", ml_home), ("away", ml_away)):
            won = _outcome(int(row["home_score"]), int(row["away_score"]), side)
            records.append({
                "season": int(row["season"]),
                "side": side,
                "ml": ml,
                "bucket": bucket_ml(ml),
                "won": won,
                "payout": _payout_for_bet(ml, won),
            })
    bet_df = pd.DataFrame.from_records(records)

    rows: list[BucketMetrics] = []
    for bucket in BUCKET_ORDER_ML:
        if bet_df.empty:
            sub = bet_df
        else:
            sub = bet_df[bet_df["bucket"] == bucket]
        wins = int((sub["won"] == True).sum()) if not sub.empty else 0  # noqa: E712
        losses = int((sub["won"] == False).sum()) if not sub.empty else 0  # noqa: E712
        pushes = int(sub["won"].isna().sum()) if not sub.empty else 0
        payouts = sub["payout"].tolist() if not sub.empty else []

        by_season: dict[int, float] = {}
        if not sub.empty:
            for season, group in sub.groupby("season"):
                w = int((group["won"] == True).sum())  # noqa: E712
                losses_ = int((group["won"] == False).sum())  # noqa: E712
                decided = w + losses_
                if decided > 0:
                    by_season[int(season)] = w / decided

        rows.append(compute_metrics(bucket, wins, losses, pushes, by_season, payouts=payouts))

    return MoneylineReport(rows=rows)
