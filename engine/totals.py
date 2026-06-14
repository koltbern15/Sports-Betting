"""Totals-by-line-bucket analysis."""

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

BUCKET_ORDER_TOTALS: list[str] = [
    "total_le_39_5",
    "total_40_42_5",
    "total_43_45_5",
    "total_46_48_5",
    "total_49_51_5",
    "total_ge_52",
]


def bucket_total(total_line: float | None) -> str | None:
    """Bucket the closing total line into 6 categories (low → high)."""
    if total_line is None:
        return None
    t = total_line
    if t <= 39.5:
        return "total_le_39_5"
    if t <= 42.5:
        return "total_40_42_5"
    if t <= 45.5:
        return "total_43_45_5"
    if t <= 48.5:
        return "total_46_48_5"
    if t <= 51.5:
        return "total_49_51_5"
    return "total_ge_52"


@dataclass
class TotalsReport:
    rows: list[BucketMetrics]


def totals_by_line_bucket(
    conn: sqlite3.Connection, season_range: tuple[int, int] | None = None
) -> TotalsReport:
    """Aggregate over/under results into the 6 total-line buckets, optionally
    limited to seasons in [lo, hi]."""
    sql = """
        SELECT g.season, b.total_close, b.total_result
        FROM games g
        JOIN betting_lines b ON b.game_id = g.game_id
        WHERE b.total_close IS NOT NULL
          AND b.total_result IS NOT NULL
    """
    params: list = []
    if season_range is not None:
        sql += " AND g.season BETWEEN ? AND ?"
        params = [season_range[0], season_range[1]]
    df = pd.read_sql_query(sql, conn, params=params or None)
    df["bucket"] = df["total_close"].apply(bucket_total)

    rows: list[BucketMetrics] = []
    for bucket in BUCKET_ORDER_TOTALS:
        sub = df[df["bucket"] == bucket]
        wins = int((sub["total_result"] == "over").sum())
        losses = int((sub["total_result"] == "under").sum())
        pushes = int((sub["total_result"] == "push").sum())

        by_season: dict[int, float] = {}
        if len(sub) > 0:
            for season, group in sub.groupby("season"):
                w = int((group["total_result"] == "over").sum())
                l_ = int((group["total_result"] == "under").sum())
                decided = w + l_
                if decided > 0:
                    by_season[int(season)] = w / decided

        rows.append(compute_metrics(bucket, wins, losses, pushes, by_season))

    return TotalsReport(rows=rows)


def _main(_argv: list[str] | None = None) -> int:
    db_path = Path("data/db/nfl_betting.sqlite")
    out_csv = Path("data/processed/totals_by_bucket.csv")
    if not db_path.exists():
        print(
            f"Database not found at {db_path}. "
            "Run `python -m ingestion.loader data/raw/spreadspoke_scores.csv` first.",
            file=sys.stderr,
        )
        return 2

    conn = connect(db_path)
    try:
        report = totals_by_line_bucket(conn)
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
