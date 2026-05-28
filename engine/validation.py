"""Real-line moneyline validation — comparator + reporting.

Compares derived ML prices (from `engine.moneyline.derive_ml_from_spread`)
to real historical ML prices stored in `real_ml_lines`. Outputs per-side
implied-probability errors plus per-bucket ROI under both price sets.
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median

from tabulate import tabulate

from engine.bucket_analysis import DISCLAIMER
from engine.db import fetch_df
from engine.moneyline import bucket_ml, derive_ml_from_spread
from engine.stats_utils import bootstrap_mean_ci, bootstrap_pvalue_mean_gt_zero


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
    """Per-bucket ROI comparison: derived prices vs real prices, same outcomes.

    `wins` and `losses` are price-invariant — game outcomes don't depend on
    which price you booked the bet at, so we store one pair rather than
    derived_wins/real_wins duplicates.
    """

    bucket: str
    n: int
    derived_roi: float
    real_roi: float
    delta_roi: float
    wins: int
    losses: int
    ci_low: float
    ci_high: float
    p_value: float
    profitable_seasons_pct: float
    by_season: dict[int, float]


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
        # NFL ties push moneyline bets — skip rather than book both sides as losses.
        if row.home_score == row.away_score:
            continue
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
                    "season": int(row.season),
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
        wins = sum(1 for r in rows if r["won"])
        losses = sum(1 for r in rows if not r["won"])
        derived_pnls = [r["derived_pnl"] for r in rows]
        real_pnls = [r["real_pnl"] for r in rows]
        derived_roi = sum(derived_pnls) / n
        real_roi = sum(real_pnls) / n

        ci_low, ci_high = bootstrap_mean_ci(real_pnls)
        p_value = bootstrap_pvalue_mean_gt_zero(real_pnls)

        season_groups: dict[int, list[float]] = defaultdict(list)
        for r in rows:
            season_groups[r["season"]].append(r["real_pnl"])
        by_season: dict[int, float] = {
            s: sum(pnls) / len(pnls) for s, pnls in season_groups.items()
        }
        if len(by_season) >= 3:
            n_profitable = sum(1 for roi_s in by_season.values() if roi_s > 0)
            profitable_seasons_pct = n_profitable / len(by_season)
        else:
            profitable_seasons_pct = math.nan

        out.append(
            BucketComparison(
                bucket=bucket,
                n=n,
                derived_roi=derived_roi,
                real_roi=real_roi,
                delta_roi=real_roi - derived_roi,
                wins=wins,
                losses=losses,
                ci_low=ci_low,
                ci_high=ci_high,
                p_value=p_value,
                profitable_seasons_pct=profitable_seasons_pct,
                by_season=by_season,
            )
        )
    out.sort(key=lambda bc: bc.bucket)
    return out


def _format_price_table(stats: dict) -> str:
    rows = [
        ["n_sides", stats["n_sides"]],
        ["mean_error_prob", f"{stats['mean_error_prob']:+.4f}"],
        ["median_abs_error_prob", f"{stats['median_abs_error_prob']:.4f}"],
        ["pct_within_2_pct_points", f"{stats['pct_within_2_pct_points']:.4f}"],
        ["pct_sign_flip", f"{stats['pct_sign_flip']:.4f}"],
        ["derived_overshades_favorites", stats["derived_overshades_favorites"]],
        ["mean_error_ml", f"{stats['mean_error_ml']:+.2f}"],
    ]
    return tabulate(rows, headers=["metric", "value"], tablefmt="github")


def _format_bucket_table(comparisons: list[BucketComparison]) -> str:
    headers = [
        "bucket", "n",
        "derived_roi", "real_roi", "delta_roi",
        "ci_low", "ci_high", "p_value", "prof_seas%",
        "W", "L",
    ]
    rows = [
        [
            bc.bucket, bc.n,
            f"{bc.derived_roi:+.4f}", f"{bc.real_roi:+.4f}", f"{bc.delta_roi:+.4f}",
            f"{bc.ci_low:+.4f}", f"{bc.ci_high:+.4f}",
            f"{bc.p_value:.4f}",
            "—" if math.isnan(bc.profitable_seasons_pct) else f"{bc.profitable_seasons_pct:.4f}",
            bc.wins, bc.losses,
        ]
        for bc in comparisons
    ]
    return tabulate(rows, headers=headers, tablefmt="github")


def write_validation_csv(report: ValidationReport, path: str | Path) -> None:
    """Write the bucket-comparison table to CSV with comment-line disclaimer + source note."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Real-line sample: source={report.source}, n_games={report.n_games}",
        f"# {DISCLAIMER}",
        "bucket,n,derived_roi,real_roi,delta_roi,wins,losses,"
        "ci_low,ci_high,p_value,profitable_seasons_pct,by_season",
    ]
    for bc in report.bucket_comparisons:
        prof = "" if math.isnan(bc.profitable_seasons_pct) else f"{bc.profitable_seasons_pct:.4f}"
        season_str = ";".join(f"{s}:{r:.4f}" for s, r in sorted(bc.by_season.items()))
        lines.append(
            f"{bc.bucket},{bc.n},"
            f"{bc.derived_roi:.6f},{bc.real_roi:.6f},{bc.delta_roi:.6f},"
            f"{bc.wins},{bc.losses},"
            f"{bc.ci_low:.6f},{bc.ci_high:.6f},{bc.p_value:.6f},"
            f"{prof},{season_str}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _main() -> int:
    """CLI: uv run python -m engine.validation"""
    from engine.db import connect

    conn = connect("data/db/nfl_betting.sqlite")
    try:
        report = compare_ml_prices(conn)
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Hint: load real ML first via `python -m ingestion.real_ml_loader <csv>`")
        return 1

    print(f"Validation report — source={report.source}, n_games={report.n_games}\n")
    print("Price-level diagnostics:")
    print(_format_price_table(report.price_stats))
    print()
    print("Bucket-ROI comparison (bucket assigned on DERIVED ML):")
    print(_format_bucket_table(report.bucket_comparisons))
    print(f"\n{DISCLAIMER}")

    out_path = Path("data/processed/ml_validation_report.csv")
    write_validation_csv(report, out_path)
    print(f"\nCSV written to {out_path}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
