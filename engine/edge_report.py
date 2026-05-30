"""Cross-market edge report.

Reads the three per-market reports (ATS, totals, moneyline-validation), and for
every bucket reports a continuous edge estimate plus the context needed to judge
whether the sample size could confirm a realistic edge. NOT a filter — every
bucket is shown, ranked by point-estimate ROI (descending).

Columns (all ROI-denominated for cross-market comparability):
  - point_roi              : realized ROI (roi_neg110 for ATS/totals, real_roi for ML)
  - ci_low / ci_high       : realized 95% CI, in ROI units
  - p_value                : realized p-value vs breakeven (exact binomial / bootstrap)
  - profitable_seasons_pct : share of seasons profitable
  - mde80_roi              : smallest TRUE edge detectable at this n (80% power, p<0.10)
  - breakeven_needed_roi   : observed edge needed for the CI lower bound to clear breakeven

The two power columns use normal-approximation analytics; the realized CI/p-value
keep their exact/bootstrap methods. For ML, the per-bet PnL std is reconstructed
from the bootstrap CI (see stats_utils.std_from_mean_ci) — a documented approximation.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from tabulate import tabulate

from engine.bucket_analysis import DISCLAIMER
from engine.stats_utils import (
    mde_mean_at_power,
    mde_winrate_at_power,
    mean_needed_for_ci,
    roi_from_win_prob,
    std_from_mean_ci,
    winrate_needed_for_ci,
)


@dataclass(frozen=True)
class EdgeRow:
    market: str
    bucket: str
    n: int
    win_rate: float  # NaN for ML (per-bet odds vary; win rate isn't meaningful)
    point_roi: float
    ci_low: float  # ROI units
    ci_high: float  # ROI units
    p_value: float
    profitable_seasons_pct: float
    mde80_roi: float
    breakeven_needed_roi: float


def _read_csv_skipping_comments(path: Path) -> list[dict]:
    """Read a CSV that may have one or more leading # comment lines."""
    if not path.exists():
        raise FileNotFoundError(f"required CSV not found: {path}")
    with path.open(encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


def _parse_float_or_nan(value: str | None) -> float:
    if value is None or value.strip() == "":
        return math.nan
    return float(value)


def _ats_or_totals_row(market: str, row: dict) -> EdgeRow:
    n = int(row["n"])
    win_rate = _parse_float_or_nan(row["win_rate"])
    point_roi = _parse_float_or_nan(row["roi_neg110"])
    # Source ci_low/ci_high are Wilson bounds on WIN RATE; express in ROI.
    ci_low = roi_from_win_prob(_parse_float_or_nan(row["ci_low"]))
    ci_high = roi_from_win_prob(_parse_float_or_nan(row["ci_high"]))
    mde80_roi = roi_from_win_prob(mde_winrate_at_power(n))
    breakeven_needed_roi = roi_from_win_prob(winrate_needed_for_ci(n))
    return EdgeRow(
        market=market,
        bucket=row["bucket"],
        n=n,
        win_rate=win_rate,
        point_roi=point_roi,
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=_parse_float_or_nan(row["p_value"]),
        profitable_seasons_pct=_parse_float_or_nan(row["profitable_seasons_pct"]),
        mde80_roi=mde80_roi,
        breakeven_needed_roi=breakeven_needed_roi,
    )


def _ml_row(row: dict) -> EdgeRow:
    n = int(row["n"])
    ci_low = _parse_float_or_nan(row["ci_low"])  # already ROI (bootstrap)
    ci_high = _parse_float_or_nan(row["ci_high"])
    # Reconstruct per-bet PnL std from the bootstrap CI (normal-theory approximation).
    std = std_from_mean_ci(ci_low, ci_high, n)
    return EdgeRow(
        market="ml",
        bucket=row["bucket"],
        n=n,
        win_rate=math.nan,
        point_roi=_parse_float_or_nan(row["real_roi"]),
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=_parse_float_or_nan(row["p_value"]),
        profitable_seasons_pct=_parse_float_or_nan(row["profitable_seasons_pct"]),
        mde80_roi=mde_mean_at_power(n, std),
        breakeven_needed_roi=mean_needed_for_ci(n, std),
    )


def build_edge_report(
    ats_path: str | Path,
    totals_path: str | Path,
    ml_path: str | Path,
) -> list[EdgeRow]:
    """Read 3 per-market CSVs, annotate every bucket, rank by point_roi desc.

    No rows are dropped. Buckets with a NaN point_roi sort to the end.
    """
    ats = [_ats_or_totals_row("ats", r) for r in _read_csv_skipping_comments(Path(ats_path))]
    tot = [_ats_or_totals_row("totals", r) for r in _read_csv_skipping_comments(Path(totals_path))]
    ml = [_ml_row(r) for r in _read_csv_skipping_comments(Path(ml_path))]
    rows = ats + tot + ml
    rows.sort(
        key=lambda r: r.point_roi if not math.isnan(r.point_roi) else float("-inf"),
        reverse=True,
    )
    return rows


DEFAULT_ATS_CSV = "data/processed/ats_by_bucket.csv"
DEFAULT_TOTALS_CSV = "data/processed/totals_by_bucket.csv"
DEFAULT_ML_CSV = "data/processed/ml_validation_report.csv"
DEFAULT_OUT_CSV = "data/processed/edge_report.csv"

_REPORT_NOTE = (
    "# Edge report: every bucket shown, ranked by point_roi desc. "
    "Not a buy signal — a measurement."
)
_POWER_NOTE = (
    "# mde80_roi = smallest TRUE edge detectable at this n (80% power, p<0.10). "
    "breakeven_needed_roi = observed edge needed for the CI lower bound to clear "
    "breakeven at this n. Power columns use normal-approximation; realized CI/"
    "p-value use exact-binomial (ATS/totals) or bootstrap (ML)."
)

_HEADER = (
    "market,bucket,n,win_rate,point_roi,ci_low,ci_high,"
    "p_value,profitable_seasons_pct,mde80_roi,breakeven_needed_roi"
)


def _fmt(x: float, prec: int = 6) -> str:
    return "" if isinstance(x, float) and math.isnan(x) else f"{x:.{prec}f}"


def _format_table(rows: list[EdgeRow]) -> str:
    headers = [
        "market", "bucket", "n", "win%", "point_roi",
        "ci_low", "ci_high", "p_value", "prof_seas%", "mde80", "be_needed",
    ]
    out = [
        [
            r.market, r.bucket, r.n,
            _fmt(r.win_rate, 4) or "—",
            f"{r.point_roi:+.4f}" if not math.isnan(r.point_roi) else "—",
            f"{r.ci_low:+.4f}" if not math.isnan(r.ci_low) else "—",
            f"{r.ci_high:+.4f}" if not math.isnan(r.ci_high) else "—",
            _fmt(r.p_value, 4) or "—",
            _fmt(r.profitable_seasons_pct, 4) or "—",
            f"{r.mde80_roi:+.4f}" if not math.isnan(r.mde80_roi) else "—",
            f"{r.breakeven_needed_roi:+.4f}" if not math.isnan(r.breakeven_needed_roi) else "—",
        ]
        for r in rows
    ]
    return tabulate(out, headers=headers, tablefmt="github")


def write_edge_report_csv(rows: list[EdgeRow], path: str | Path) -> None:
    """Write the ranked edge report to CSV with explanatory notes + disclaimer."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_REPORT_NOTE, _POWER_NOTE, f"# {DISCLAIMER}", _HEADER]
    for r in rows:
        lines.append(
            f"{r.market},{r.bucket},{r.n},"
            f"{_fmt(r.win_rate)},{_fmt(r.point_roi)},"
            f"{_fmt(r.ci_low)},{_fmt(r.ci_high)},"
            f"{_fmt(r.p_value)},{_fmt(r.profitable_seasons_pct, 4)},"
            f"{_fmt(r.mde80_roi)},{_fmt(r.breakeven_needed_roi)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _main() -> int:
    """CLI: uv run python -m engine.edge_report"""
    try:
        rows = build_edge_report(DEFAULT_ATS_CSV, DEFAULT_TOTALS_CSV, DEFAULT_ML_CSV)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Hint: run `uv run python -m engine.ats`, `uv run python -m engine.totals`, "
              "and `uv run python -m engine.validation` first.")
        return 1

    print(f"Edge report across all 3 markets ({len(rows)} buckets, ranked by point_roi):\n")
    print(_format_table(rows))
    write_edge_report_csv(rows, DEFAULT_OUT_CSV)
    print(f"\n{DISCLAIMER}")
    print(f"\nCSV written to {DEFAULT_OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
