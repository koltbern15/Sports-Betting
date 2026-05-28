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

MIN_N = 100
MIN_CI_LOW = 0.0
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


def _passes(norm: dict) -> bool:
    if norm["n"] < MIN_N:
        return False
    if math.isnan(norm["ci_low"]) or norm["ci_low"] <= MIN_CI_LOW:
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
