"""Shared bucket-analysis machinery used by ATS, totals, and moneyline modules.

Owns the BucketMetrics dataclass, the metrics-computation helper, the table
formatter, the CSV writer, and the disclaimer. All three analysis modules
delegate display/serialization to this module so output stays consistent.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from tabulate import tabulate

from engine.stats_utils import (
    BREAKEVEN_AT_NEG_110,
    binomial_pvalue,
    dollar_weighted_roi,
    roi,
    wilson_ci,
)

INSUFFICIENT_SAMPLE_THRESHOLD = 50

DISCLAIMER = (
    "Past performance does not guarantee future results. "
    "This tool is for informational purposes only. Gamble responsibly."
)


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


def compute_metrics(
    bucket: str,
    wins: int,
    losses: int,
    pushes: int,
    by_season: dict[int, float] | None = None,
    *,
    payouts: list[float] | None = None,
) -> BucketMetrics:
    """Aggregate win/loss/push counts into a fully-specified metrics row.

    If `payouts` is supplied, both ROI columns use dollar_weighted_roi(payouts)
    instead of fixed -110/-105 ROI from the win count. The two columns will
    then be identical.
    """
    n = wins + losses + pushes
    decided = wins + losses
    win_rate = (wins / decided) if decided > 0 else 0.0
    push_rate = (pushes / n) if n > 0 else 0.0
    p = binomial_pvalue(wins, decided, BREAKEVEN_AT_NEG_110)
    lo, hi = wilson_ci(wins, decided)
    if payouts is not None:
        roi_110 = dollar_weighted_roi(payouts)
        roi_105 = roi_110
    else:
        roi_110 = roi(wins, losses, pushes, -110)
        roi_105 = roi(wins, losses, pushes, -105)
    return BucketMetrics(
        bucket=bucket,
        n=n,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=win_rate,
        push_rate=push_rate,
        roi_neg110=roi_110,
        roi_neg105=roi_105,
        p_value=p,
        ci_low=lo,
        ci_high=hi,
        insufficient_sample=decided < INSUFFICIENT_SAMPLE_THRESHOLD,
        by_season=by_season or {},
    )


def format_table(rows: list[BucketMetrics]) -> str:
    """Render BucketMetrics rows as a GitHub-flavored tabulate table."""
    headers = [
        "bucket", "n", "W", "L", "P",
        "win%", "push%", "ROI -110", "ROI -105",
        "p-value", "CI low", "CI high", "low_n?",
    ]
    out_rows = []
    for r in rows:
        out_rows.append([
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
    return tabulate(out_rows, headers=headers, tablefmt="github")


def write_csv(rows: list[BucketMetrics], out_path: Path) -> None:
    """Write BucketMetrics rows to a CSV. Adds a disclaimer comment as line 1."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        f.write(f"# {DISCLAIMER}\n")
        writer = csv.writer(f)
        writer.writerow([
            "bucket", "n", "wins", "losses", "pushes",
            "win_rate", "push_rate", "roi_neg110", "roi_neg105",
            "p_value", "ci_low", "ci_high", "insufficient_sample",
            "by_season",
        ])
        for r in rows:
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
