"""ATS-by-spread-bucket analysis.

Buckets the home-perspective signed spread into the 11 categories defined in
the Slice 1 spec, then aggregates wins / losses / pushes / metrics per bucket.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from tabulate import tabulate

from engine.db import connect
from engine.stats_utils import (
    BREAKEVEN_AT_NEG_110,
    binomial_pvalue,
    roi,
    wilson_ci,
)

# Bucket order is the order they will appear in the final report (favorites → dogs).
BUCKET_ORDER: list[str] = [
    "home_fav_14.5+",
    "home_fav_10.5_14",
    "home_fav_7.5_10",
    "home_fav_3.5_7",
    "home_fav_1_3",
    "pickem",
    "home_dog_1_3",
    "home_dog_3.5_7",
    "home_dog_7.5_10",
    "home_dog_10.5_14",
    "home_dog_14.5+",
]


def bucket_spread(spread_home_close: float | None) -> str | None:
    """Bucket the home-perspective spread.

    Pick'em covers (-0.5, 0, 0.5). Favorites and underdogs partition the rest.
    """
    if spread_home_close is None:
        return None
    s = spread_home_close
    if -0.5 <= s <= 0.5:
        return "pickem"
    if s < 0:
        m = -s  # magnitude when home is favored
        if m >= 14.5:
            return "home_fav_14.5+"
        if m >= 10.5:
            return "home_fav_10.5_14"
        if m >= 7.5:
            return "home_fav_7.5_10"
        if m >= 3.5:
            return "home_fav_3.5_7"
        return "home_fav_1_3"
    # s > 0.5 → home is the dog
    if s >= 14.5:
        return "home_dog_14.5+"
    if s >= 10.5:
        return "home_dog_10.5_14"
    if s >= 7.5:
        return "home_dog_7.5_10"
    if s >= 3.5:
        return "home_dog_3.5_7"
    return "home_dog_1_3"


@dataclass
class BucketMetrics:
    bucket: str
    n: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    push_rate: float
    roi_neg110: float
    roi_neg105: float
    p_value: float
    ci_low: float
    ci_high: float
    insufficient_sample: bool
    by_season: dict[int, float] = field(default_factory=dict)


def compute_bucket_metrics(
    bucket: str,
    covers: int,
    losses: int,
    pushes: int,
    by_season: dict[int, float] | None = None,
) -> BucketMetrics:
    """Aggregate cover/loss/push counts into a fully-specified metrics row."""
    n = covers + losses + pushes
    decided = covers + losses
    win_rate = (covers / decided) if decided > 0 else 0.0
    push_rate = (pushes / n) if n > 0 else 0.0
    p = binomial_pvalue(covers, decided, BREAKEVEN_AT_NEG_110)
    lo, hi = wilson_ci(covers, decided)
    return BucketMetrics(
        bucket=bucket,
        n=n,
        wins=covers,
        losses=losses,
        pushes=pushes,
        win_rate=win_rate,
        push_rate=push_rate,
        roi_neg110=roi(covers, losses, pushes, -110),
        roi_neg105=roi(covers, losses, pushes, -105),
        p_value=p,
        ci_low=lo,
        ci_high=hi,
        insufficient_sample=decided < 50,
        by_season=by_season or {},
    )


@dataclass
class AtsReport:
    rows: list[BucketMetrics]


def ats_by_spread_bucket(conn: sqlite3.Connection) -> AtsReport:
    """Aggregate ATS results into the 11 home-spread buckets.

    Joins games and betting_lines on game_id, drops rows where
    spread_home_close or home_spread_result is NULL.
    """
    df = pd.read_sql_query(
        """
        SELECT g.season, b.spread_home_close, b.home_spread_result
        FROM games g
        JOIN betting_lines b ON b.game_id = g.game_id
        WHERE b.spread_home_close IS NOT NULL
          AND b.home_spread_result IS NOT NULL
        """,
        conn,
    )
    df["bucket"] = df["spread_home_close"].apply(bucket_spread)

    rows: list[BucketMetrics] = []
    for bucket in BUCKET_ORDER:
        sub = df[df["bucket"] == bucket]
        covers = int((sub["home_spread_result"] == "cover").sum())
        losses = int((sub["home_spread_result"] == "loss").sum())
        pushes = int((sub["home_spread_result"] == "push").sum())

        by_season: dict[int, float] = {}
        if len(sub) > 0:
            for season, group in sub.groupby("season"):
                c = int((group["home_spread_result"] == "cover").sum())
                losses_ = int((group["home_spread_result"] == "loss").sum())
                decided = c + losses_
                if decided > 0:
                    by_season[int(season)] = c / decided

        rows.append(compute_bucket_metrics(bucket, covers, losses, pushes, by_season))

    return AtsReport(rows=rows)


DISCLAIMER = (
    "Past performance does not guarantee future results. "
    "This tool is for informational purposes only. Gamble responsibly."
)


def format_report(report: AtsReport) -> str:
    """Format the report as a tabulated table for stdout."""
    headers = [
        "bucket", "n", "W", "L", "P",
        "win%", "push%", "ROI -110", "ROI -105",
        "p-value", "CI low", "CI high", "low_n?",
    ]
    rows = []
    for r in report.rows:
        rows.append([
            r.bucket, r.n, r.wins, r.losses, r.pushes,
            f"{r.win_rate:.4f}" if r.n else "—",
            f"{r.push_rate:.4f}" if r.n else "—",
            f"{r.roi_neg110:+.4f}" if r.n else "—",
            f"{r.roi_neg105:+.4f}" if r.n else "—",
            f"{r.p_value:.4f}",
            f"{r.ci_low:.4f}",
            f"{r.ci_high:.4f}",
            "*" if r.insufficient_sample else "",
        ])
    return tabulate(rows, headers=headers, tablefmt="github")


def write_csv(report: AtsReport, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        # Disclaimer comment line at the top of the CSV
        f.write(f"# {DISCLAIMER}\n")
        writer = csv.writer(f)
        writer.writerow([
            "bucket", "n", "wins", "losses", "pushes",
            "win_rate", "push_rate", "roi_neg110", "roi_neg105",
            "p_value", "ci_low", "ci_high", "insufficient_sample",
            "by_season",
        ])
        for r in report.rows:
            writer.writerow([
                r.bucket, r.n, r.wins, r.losses, r.pushes,
                f"{r.win_rate:.6f}",
                f"{r.push_rate:.6f}",
                f"{r.roi_neg110:.6f}",
                f"{r.roi_neg105:.6f}",
                f"{r.p_value:.6f}",
                f"{r.ci_low:.6f}",
                f"{r.ci_high:.6f}",
                int(r.insufficient_sample),
                ";".join(f"{s}:{w:.4f}" for s, w in sorted(r.by_season.items())),
            ])


def _main(_argv: list[str] | None = None) -> int:
    db_path = Path("data/db/nfl_betting.sqlite")
    out_csv = Path("data/processed/ats_by_bucket.csv")
    if not db_path.exists():
        print(
            f"Database not found at {db_path}. "
            "Run `python -m ingestion.loader data/raw/spreadspoke_scores.csv` first.",
            file=sys.stderr,
        )
        return 2

    conn = connect(db_path)
    try:
        report = ats_by_spread_bucket(conn)
    finally:
        conn.close()

    print(format_report(report))
    print()
    print(DISCLAIMER)

    write_csv(report, out_csv)
    print(f"\nCSV written to {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
