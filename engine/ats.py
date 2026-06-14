"""ATS-by-spread-bucket analysis.

Buckets the home-perspective signed spread into the 11 categories defined in
the Slice 1 spec, then aggregates wins / losses / pushes / metrics per bucket.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from engine.bucket_analysis import (
    DISCLAIMER,
    BucketMetrics,
    compute_metrics,
    format_table,
    write_csv,
)
from engine.db import connect

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
        m = -s
        if m >= 14.5:
            return "home_fav_14.5+"
        if m >= 10.5:
            return "home_fav_10.5_14"
        if m >= 7.5:
            return "home_fav_7.5_10"
        if m >= 3.5:
            return "home_fav_3.5_7"
        return "home_fav_1_3"
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
class AtsReport:
    rows: list[BucketMetrics]


def ats_by_spread_bucket(
    conn: sqlite3.Connection, season_range: tuple[int, int] | None = None
) -> AtsReport:
    """Aggregate ATS results into the 11 home-spread buckets, optionally limited
    to seasons in [lo, hi]."""
    sql = """
        SELECT g.season, b.spread_home_close, b.home_spread_result
        FROM games g
        JOIN betting_lines b ON b.game_id = g.game_id
        WHERE b.spread_home_close IS NOT NULL
          AND b.home_spread_result IS NOT NULL
    """
    params: list = []
    if season_range is not None:
        sql += " AND g.season BETWEEN ? AND ?"
        params = [season_range[0], season_range[1]]
    df = pd.read_sql_query(sql, conn, params=params or None)
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

        rows.append(compute_metrics(bucket, covers, losses, pushes, by_season))

    return AtsReport(rows=rows)


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

    print(format_table(report.rows))
    print()
    print(DISCLAIMER)

    write_csv(report.rows, out_csv)
    print(f"\nCSV written to {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
