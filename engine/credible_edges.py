"""Cross-market credible-edges ranker.

Reads the three per-market reports (ATS, totals, moneyline-validation),
filters each bucket by four credibility thresholds, ranks survivors by
Wilson lower bound (descending), and outputs a single CSV.

The thresholds defining a "credible" edge:
  - n >= 100               (sample size floor)
  - ci_low > 0             (95% confident the true edge is positive)
  - p_value < 0.10         (modest evidence vs breakeven)
  - profitable_seasons_pct >= 0.60   (stable across time)

For ML buckets, `roi` is the real_roi from Slice 3 — derived prices are
biased per the Slice 3 finding.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from tabulate import tabulate

from engine.bucket_analysis import DISCLAIMER

MIN_N = 100
# ci_low threshold is market-aware:
#   - ATS/totals: ci_low is the Wilson CI lower bound on WIN RATE (a [0,1]
#     proportion). The threshold is "win-rate floor strictly above -110 breakeven"
#     since every ATS/totals bet is priced at -110.
#   - ML: ci_low is the bootstrap CI lower bound on real ROI (mean PnL, centered
#     near 0). The threshold is "ROI floor strictly above 0".
MIN_CI_LOW_WIN_RATE = 110 / 210  # BREAKEVEN_AT_NEG_110 ~= 0.5238
MIN_CI_LOW_ROI = 0.0
MAX_P_VALUE = 0.10
MIN_PROFITABLE_SEASONS_PCT = 0.60


@dataclass(frozen=True)
class CredibleEdge:
    market: str
    bucket: str
    n: int
    roi: float
    ci_low: float
    ci_high: float
    p_value: float
    profitable_seasons_pct: float


def _read_csv_skipping_comments(path: Path) -> list[dict]:
    """Read a CSV that may have one or more leading # comment lines."""
    if not path.exists():
        raise FileNotFoundError(f"required CSV not found: {path}")
    with path.open(encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    return list(reader)


def _parse_float_or_nan(value: str | None) -> float:
    if value is None or value.strip() == "":
        return math.nan
    return float(value)


def _normalize_ats_or_totals(market: str, row: dict) -> dict:
    return {
        "market": market,
        "bucket": row["bucket"],
        "n": int(row["n"]),
        "roi": _parse_float_or_nan(row["roi_neg110"]),
        "ci_low": _parse_float_or_nan(row["ci_low"]),
        "ci_high": _parse_float_or_nan(row["ci_high"]),
        "p_value": _parse_float_or_nan(row["p_value"]),
        "profitable_seasons_pct": _parse_float_or_nan(row["profitable_seasons_pct"]),
    }


def _normalize_ml(row: dict) -> dict:
    return {
        "market": "ml",
        "bucket": row["bucket"],
        "n": int(row["n"]),
        "roi": _parse_float_or_nan(row["real_roi"]),
        "ci_low": _parse_float_or_nan(row["ci_low"]),
        "ci_high": _parse_float_or_nan(row["ci_high"]),
        "p_value": _parse_float_or_nan(row["p_value"]),
        "profitable_seasons_pct": _parse_float_or_nan(row["profitable_seasons_pct"]),
    }


def _ci_low_threshold(market: str) -> float:
    """Pick the ci_low floor based on what ci_low measures in each market.

    ATS/totals' ci_low is a Wilson CI on win rate (compare to -110 breakeven).
    ML's ci_low is a bootstrap CI on real ROI (compare to 0).
    """
    if market == "ml":
        return MIN_CI_LOW_ROI
    return MIN_CI_LOW_WIN_RATE


def _passes(norm: dict) -> bool:
    if norm["n"] < MIN_N:
        return False
    ci_threshold = _ci_low_threshold(norm["market"])
    if math.isnan(norm["ci_low"]) or norm["ci_low"] <= ci_threshold:
        return False
    if math.isnan(norm["p_value"]) or norm["p_value"] >= MAX_P_VALUE:
        return False
    prof = norm["profitable_seasons_pct"]
    if math.isnan(prof) or prof < MIN_PROFITABLE_SEASONS_PCT:
        return False
    return True


def rank_credible_edges(
    ats_path: str | Path,
    totals_path: str | Path,
    ml_path: str | Path,
) -> list[CredibleEdge]:
    """Read 3 per-market CSVs, filter by credibility thresholds, rank by ci_low desc."""
    ats_raw = _read_csv_skipping_comments(Path(ats_path))
    ats_rows = [_normalize_ats_or_totals("ats", r) for r in ats_raw]
    tot_raw = _read_csv_skipping_comments(Path(totals_path))
    tot_rows = [_normalize_ats_or_totals("totals", r) for r in tot_raw]
    ml_rows = [_normalize_ml(r) for r in _read_csv_skipping_comments(Path(ml_path))]

    survivors = [r for r in (ats_rows + tot_rows + ml_rows) if _passes(r)]
    survivors.sort(key=lambda r: r["ci_low"], reverse=True)
    return [
        CredibleEdge(
            market=r["market"],
            bucket=r["bucket"],
            n=r["n"],
            roi=r["roi"],
            ci_low=r["ci_low"],
            ci_high=r["ci_high"],
            p_value=r["p_value"],
            profitable_seasons_pct=r["profitable_seasons_pct"],
        )
        for r in survivors
    ]


DEFAULT_ATS_CSV = "data/processed/ats_by_bucket.csv"
DEFAULT_TOTALS_CSV = "data/processed/totals_by_bucket.csv"
DEFAULT_ML_CSV = "data/processed/ml_validation_report.csv"
DEFAULT_OUT_CSV = "data/processed/credible_edges.csv"

_THRESHOLD_NOTE = (
    f"# Credible-edge thresholds: n>={MIN_N}, "
    f"ATS/totals ci_low>{MIN_CI_LOW_WIN_RATE:.4f} (win-rate vs -110 breakeven), "
    f"ML ci_low>{MIN_CI_LOW_ROI} (real ROI), "
    f"p<{MAX_P_VALUE}, profitable_seasons>={MIN_PROFITABLE_SEASONS_PCT}. "
    f"Ranked by ci_low desc."
)


def _format_edges_table(edges: list[CredibleEdge]) -> str:
    headers = ["market", "bucket", "n", "roi", "ci_low", "ci_high", "p_value", "prof_seas%"]
    rows = [
        [
            e.market, e.bucket, e.n,
            f"{e.roi:+.4f}",
            f"{e.ci_low:+.4f}",
            f"{e.ci_high:+.4f}",
            f"{e.p_value:.4f}",
            f"{e.profitable_seasons_pct:.4f}",
        ]
        for e in edges
    ]
    return tabulate(rows, headers=headers, tablefmt="github")


def write_credible_edges_csv(edges: list[CredibleEdge], path: str | Path) -> None:
    """Write the ranked credible-edges to CSV with threshold note + disclaimer."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        _THRESHOLD_NOTE,
        f"# {DISCLAIMER}",
        "market,bucket,n,roi,ci_low,ci_high,p_value,profitable_seasons_pct",
    ]
    for e in edges:
        lines.append(
            f"{e.market},{e.bucket},{e.n},"
            f"{e.roi:.6f},{e.ci_low:.6f},{e.ci_high:.6f},"
            f"{e.p_value:.6f},{e.profitable_seasons_pct:.4f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _main() -> int:
    """CLI: uv run python -m engine.credible_edges"""
    try:
        edges = rank_credible_edges(DEFAULT_ATS_CSV, DEFAULT_TOTALS_CSV, DEFAULT_ML_CSV)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Hint: run `uv run python -m engine.ats`, `uv run python -m engine.totals`, "
              "and `uv run python -m engine.validation` first.")
        return 1

    if not edges:
        print("No buckets meet credibility thresholds.")
        print(_THRESHOLD_NOTE[2:])  # strip leading "# "
    else:
        print(f"Credible edges across all 3 markets ({len(edges)} survivors):\n")
        print(_format_edges_table(edges))

    write_credible_edges_csv(edges, DEFAULT_OUT_CSV)
    print(f"\n{DISCLAIMER}")
    print(f"\nCSV written to {DEFAULT_OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
