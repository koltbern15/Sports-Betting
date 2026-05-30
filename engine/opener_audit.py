"""Pure audit math for opening-line data quality. No I/O."""

from __future__ import annotations

import math
from statistics import mean, pstdev


def agreement_rate(a: list[float | None], b: list[float | None], *, tol: float) -> float:
    """Share of comparable (both non-None) pairs whose |a-b| <= tol. NaN if none comparable."""
    pairs = [(x, y) for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    if not pairs:
        return math.nan
    agree = sum(1 for x, y in pairs if abs(x - y) <= tol)
    return agree / len(pairs)


def movement_stats(opens: list[float | None], closes: list[float | None]) -> dict:
    """Stats on (close - open) over comparable pairs."""
    diffs = [
        c - o
        for o, c in zip(opens, closes, strict=True)
        if o is not None and c is not None
    ]
    if not diffs:
        return {"n": 0, "mean": math.nan, "stdev": math.nan}
    return {"n": len(diffs), "mean": mean(diffs), "stdev": pstdev(diffs) if len(diffs) > 1 else 0.0}


def outliers(
    opens: list[float | None], closes: list[float | None], *, threshold: float
) -> list[int]:
    """Indices where |close - open| exceeds threshold (both non-None)."""
    out = []
    for i, (o, c) in enumerate(zip(opens, closes, strict=True)):
        if o is not None and c is not None and abs(c - o) > threshold:
            out.append(i)
    return out
