"""Totals-by-line-bucket analysis."""

from __future__ import annotations

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
