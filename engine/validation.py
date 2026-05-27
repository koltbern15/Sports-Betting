"""Real-line moneyline validation — comparator + reporting.

Compares derived ML prices (from `engine.moneyline.derive_ml_from_spread`)
to real historical ML prices stored in `real_ml_lines`. Outputs per-side
implied-probability errors plus per-bucket ROI under both price sets.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median

from engine.db import fetch_df
from engine.moneyline import bucket_ml, derive_ml_from_spread


def american_to_implied_prob(ml: int) -> float:
    """Convert integer American odds to raw implied probability (vig included)."""
    if ml < 0:
        return (-ml) / ((-ml) + 100)
    return 100 / (ml + 100)


def side_error(real_ml: int, derived_ml: int) -> dict:
    """Per-side comparison: error in implied-probability points and raw American delta.

    Returns {"error_prob": float, "error_ml": int}
      error_prob = real_implied_p - derived_implied_p
        (positive => real market priced this side as more likely than derived)
      error_ml   = real_ml - derived_ml (raw American-odds delta, for readability)
    """
    return {
        "error_prob": american_to_implied_prob(real_ml) - american_to_implied_prob(derived_ml),
        "error_ml": real_ml - derived_ml,
    }


def compute_price_stats(sides: list[dict]) -> dict:
    """Aggregate per-side comparisons into summary stats.

    Each side dict must contain: real_ml, derived_ml, is_favorite (bool).
    """
    if not sides:
        raise ValueError("compute_price_stats called with empty sides list")

    errors = [side_error(s["real_ml"], s["derived_ml"]) for s in sides]
    errs_prob = [e["error_prob"] for e in errors]
    errs_ml = [e["error_ml"] for e in errors]

    n_sides = len(sides)
    n_within = sum(1 for e in errs_prob if abs(e) <= 0.02)

    sign_flips = 0
    for side, _err in zip(sides, errs_prob, strict=True):
        real_p = american_to_implied_prob(side["real_ml"])
        derived_p = american_to_implied_prob(side["derived_ml"])
        if (real_p > 0.5) != (derived_p > 0.5):
            sign_flips += 1

    fav_errors = [
        e["error_prob"] for e, s in zip(errors, sides, strict=True) if s["is_favorite"]
    ]
    if fav_errors:
        mean_fav_err = mean(fav_errors)
        pct_share_sign = sum(1 for e in fav_errors if e < 0) / len(fav_errors)
        overshades = mean_fav_err < 0 and pct_share_sign > 0.6
    else:
        overshades = False

    return {
        "n_sides": n_sides,
        "mean_error_prob": mean(errs_prob),
        "median_abs_error_prob": median(abs(e) for e in errs_prob),
        "pct_within_2_pct_points": n_within / n_sides,
        "pct_sign_flip": sign_flips / n_sides,
        "derived_overshades_favorites": overshades,
        "mean_error_ml": mean(errs_ml),
    }


@dataclass(frozen=True)
class BucketComparison:
    """Per-bucket ROI comparison: derived prices vs real prices, same outcomes."""

    bucket: str
    n: int
    derived_roi: float
    real_roi: float
    delta_roi: float
    derived_wins: int
    derived_losses: int
    real_wins: int
    real_losses: int


@dataclass(frozen=True)
class ValidationReport:
    """End-to-end output of compare_ml_prices."""

    price_stats: dict
    bucket_comparisons: list[BucketComparison]
    source: str
    n_games: int


_SQL = """
SELECT g.game_id, g.season, g.home_team, g.away_team,
       g.home_score, g.away_score,
       bl.spread_home_close,
       r.ml_home_real, r.ml_away_real, r.source
FROM real_ml_lines r
JOIN games g          ON g.game_id = r.game_id
JOIN betting_lines bl ON bl.game_id = r.game_id
WHERE g.home_score IS NOT NULL
  AND g.away_score IS NOT NULL
  AND bl.spread_home_close IS NOT NULL
"""


def _payout(ml: int, won: bool) -> float:
    """PnL on $1 stake at the given American odds. Pushes not supported."""
    if not won:
        return -1.0
    if ml < 0:
        return 100.0 / (-ml)
    return ml / 100.0


def compare_ml_prices(conn: sqlite3.Connection) -> ValidationReport:
    """Build the validation report — joins real ML to games + spreads, recomputes derived ML."""
    df = fetch_df(conn, _SQL)
    if len(df) == 0:
        raise ValueError("insufficient validation data — real_ml_lines is empty or unjoinable")

    sides: list[dict] = []
    bucket_rows: list[dict] = []

    for row in df.itertuples(index=False):
        derived = derive_ml_from_spread(row.spread_home_close)
        if derived is None:
            continue
        derived_home, derived_away = derived
        home_won = row.home_score > row.away_score
        away_won = row.away_score > row.home_score

        for _side_name, derived_ml, real_ml, won in (
            ("home", derived_home, int(row.ml_home_real), home_won),
            ("away", derived_away, int(row.ml_away_real), away_won),
        ):
            sides.append(
                {"real_ml": real_ml, "derived_ml": derived_ml, "is_favorite": derived_ml < 0}
            )
            bucket = bucket_ml(derived_ml)
            if bucket is None:
                continue
            bucket_rows.append(
                {
                    "bucket": bucket,
                    "won": won,
                    "derived_pnl": _payout(derived_ml, won),
                    "real_pnl": _payout(real_ml, won),
                }
            )

    price_stats = compute_price_stats(sides)
    bucket_comparisons = _build_bucket_comparisons(bucket_rows)
    source = str(df["source"].mode().iloc[0]) if len(df) else "unknown"
    return ValidationReport(
        price_stats=price_stats,
        bucket_comparisons=bucket_comparisons,
        source=source,
        n_games=int(df["game_id"].nunique()),
    )


def _build_bucket_comparisons(bucket_rows: list[dict]) -> list[BucketComparison]:
    """Aggregate per-bet rows into per-bucket comparison records."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in bucket_rows:
        grouped[row["bucket"]].append(row)
    out: list[BucketComparison] = []
    for bucket, rows in grouped.items():
        n = len(rows)
        derived_wins = sum(1 for r in rows if r["won"] and r["derived_pnl"] > 0)
        derived_losses = sum(1 for r in rows if not r["won"])
        real_wins = sum(1 for r in rows if r["won"] and r["real_pnl"] > 0)
        real_losses = sum(1 for r in rows if not r["won"])
        derived_roi = sum(r["derived_pnl"] for r in rows) / n
        real_roi = sum(r["real_pnl"] for r in rows) / n
        out.append(
            BucketComparison(
                bucket=bucket,
                n=n,
                derived_roi=derived_roi,
                real_roi=real_roi,
                delta_roi=real_roi - derived_roi,
                derived_wins=derived_wins,
                derived_losses=derived_losses,
                real_wins=real_wins,
                real_losses=real_losses,
            )
        )
    out.sort(key=lambda bc: bc.bucket)
    return out
